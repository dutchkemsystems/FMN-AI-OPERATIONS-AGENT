"""Multi-Agent Reinforcement Learning (MARL) Core.

Provides training via Stable-Baselines3 PPO when available, otherwise
a parameter-grid-search over the digital twin (heuristic fallback).
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..models.database import RLPolicy, SessionLocal, utcnow
from ..utils.helpers import new_id

logger = logging.getLogger("fmn.marl")

ACTIONS = ("conservative", "balanced", "aggressive")


@dataclass
class TwinParams:
    days: int = 7
    seed: int = 42
    fx_usd_ngn: float = 1500.0
    wheat_usd_per_ton: float = 260.0
    cassava_substitution: float = 0.15
    diesel_price_per_litre: float = 850.0
    grid_tariff_per_kwh: float = 65.0
    gas_tariff_per_kwh: float = 45.0
    solar_capacity_kw: float = 1200.0
    mill_throughput_tph: float = 120.0
    fleet_size: int = 60
    demand_tons_per_day: float = 900.0
    demand_multiplier: float = 1.0
    fx_shock_pct: float = 0.0
    wheat_shock_pct: float = 0.0
    fuel_shock_pct: float = 0.0
    port_closure_days: int = 0
    disruption_probability: float = 0.08
    base_waste_pct: float = 6.0


def _to_obs(params: TwinParams) -> list[float]:
    return [
        params.fx_usd_ngn / 2000.0,
        params.wheat_usd_per_ton / 400.0,
        params.diesel_price_per_litre / 1000.0,
        params.demand_multiplier,
    ]


def _eval_heuristic(action_idx: int, days: int = 14, seed: int = 42) -> float:
    """Evaluate a discrete action by running the digital twin."""
    from ..digital_twin.simulator import simulate

    multipliers = (0.8, 1.0, 1.25)
    params = TwinParams(days=days, seed=seed, demand_multiplier=multipliers[action_idx])
    result = simulate(params)
    return -(result.risk_score / 50.0) + result.kpis.get("avg_service_level", 0.8)


class FmnEnv:
    """Lightweight gymnasium-compatible environment wrapping the digital twin."""

    def __init__(self, days: int = 7) -> None:
        self.days = days
        self._params = TwinParams(days=days)
        self._step = 0

    def reset(self, seed: int | None = None, options: dict | None = None):
        if seed is not None:
            import random
            random.seed(seed)
        self._params = TwinParams(days=self.days, seed=seed or 42)
        self._step = 0
        return _to_obs(self._params), {}

    def step(self, action: int):
        from ..digital_twin.simulator import simulate

        multipliers = (0.8, 1.0, 1.25)
        self._params = replace(
            self._params,
            demand_multiplier=multipliers[int(action) % 3],
            seed=self._params.seed + self._step,
        )
        result = simulate(self._params)
        reward = result.kpis.get("avg_service_level", 0.8) - result.risk_score / 50.0
        self._step += 1
        done = self._step >= self.days
        return _to_obs(self._params), reward, done, {"risk": result.risk_score}


class MARLCore:
    """Central training environment for multi-agent policies."""

    def __init__(
        self,
        settings: Any | None = None,
        session_factory: Any | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory
        self.backend = "heuristic"
        try:
            import stable_baselines3  # noqa: F401

            self.backend = "sb3"
        except ImportError:
            pass
        self._model_dir = Path("models_artifacts")
        self._model_dir.mkdir(parents=True, exist_ok=True)

    def train(self, total_timesteps: int = 20000) -> dict:
        if self.backend == "sb3":
            return self._train_sb3(total_timesteps)
        return self._train_heuristic()

    def _train_sb3(self, timesteps: int) -> dict:
        from stable_baselines3 import PPO
        from stable_baselines3.common.env_util import make_vec_env

        env = make_vec_env(FmnEnv)
        model = PPO("MlpPolicy", env, verbose=0)
        model.learn(total_timesteps=timesteps)
        path = str(self._model_dir / "marl_ppo")
        model.save(path)
        score = self._evaluate_sb3(model)
        return self._persist_policy(
            {"backend": "sb3", "artifact": path},
            score,
            path,
        )

    def _evaluate_sb3(self, model: Any) -> float:
        env = FmnEnv(days=7)
        obs, _ = env.reset(seed=99)
        total = 0.0
        for _ in range(7):
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, done, _ = env.step(int(action))
            total += reward
            if done:
                break
        return total / 7.0

    def _train_heuristic(self) -> dict:
        best: tuple[dict, float] | None = None
        for idx in range(3):
            score = _eval_heuristic(idx)
            candidate = {"best_action": idx, "action_name": ACTIONS[idx], "backend": "heuristic"}
            if best is None or score > best[1]:
                best = (candidate, score)

        params, score = best  # type: ignore[misc]
        path = str(self._model_dir / "marl_heuristic.json")
        with open(path, "w") as f:
            json.dump(params, f)
        return self._persist_policy(params, score, path)

    def _persist_policy(self, params: dict, score: float, artifact: str) -> dict:
        if not self.session_factory:
            return {"params": params, "score": score}

        db = self.session_factory()
        try:
            db.query(RLPolicy).filter_by(agent_type="global").update({"active": False})
            policy = RLPolicy(
                agent_type="global",
                version=f"v{int(utcnow().timestamp())}",
                artifact_path=artifact,
                parameters=params,
                performance_score=round(float(score), 4),
                active=True,
            )
            db.add(policy)
            db.commit()
        finally:
            db.close()

        return {"params": params, "score": round(float(score), 4), "artifact": artifact}

    def infer(self, agent_type: str = "global") -> int | None:
        if not self.session_factory:
            return None
        db = self.session_factory()
        try:
            policy = (
                db.query(RLPolicy)
                .filter_by(agent_type=agent_type, active=True)
                .order_by(RLPolicy.created_at.desc())
                .first()
            )
            if policy and policy.parameters:
                return policy.parameters.get("best_action")
        finally:
            db.close()
        return None
