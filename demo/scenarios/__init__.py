"""Scripted scenario suite for validating HEBBS capabilities via gRPC."""

from demo.scenarios.base import Scenario, ScenarioResult, Assertion
from demo.scenarios.discovery_call import DiscoveryCallScenario
from demo.scenarios.objection_handling import ObjectionHandlingScenario
from demo.scenarios.multi_session import MultiSessionScenario
from demo.scenarios.reflect_learning import ReflectLearningScenario
from demo.scenarios.subscribe_realtime import SubscribeRealtimeScenario
from demo.scenarios.forget_gdpr import ForgetGdprScenario
from demo.scenarios.multi_entity import MultiEntityScenario

ALL_SCENARIOS: dict[str, type[Scenario]] = {
    "discovery_call": DiscoveryCallScenario,
    "objection_handling": ObjectionHandlingScenario,
    "multi_session": MultiSessionScenario,
    "reflect_learning": ReflectLearningScenario,
    "subscribe_realtime": SubscribeRealtimeScenario,
    "forget_gdpr": ForgetGdprScenario,
    "multi_entity": MultiEntityScenario,
}

__all__ = [
    "Scenario",
    "ScenarioResult",
    "Assertion",
    "ALL_SCENARIOS",
    "DiscoveryCallScenario",
    "ObjectionHandlingScenario",
    "MultiSessionScenario",
    "ReflectLearningScenario",
    "SubscribeRealtimeScenario",
    "ForgetGdprScenario",
    "MultiEntityScenario",
]
