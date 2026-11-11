import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Configure enterprise-grade logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("API Gateway")


@dataclass
class DashboardResponse:
    user_id: int
    profile: Optional[Dict[str, Any]] = None
    inventory: Optional[Dict[str, Any]] = None
    pricing: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)


# --- Simulated Microservice Clients ---


async def fetch_user_profile(user_id: int) -> dict:
    await asyncio.sleep(0.3)  # Simulate network IO
    if user_id == 999:  # Simulate a sudden microservice outage
        raise ConnectionError("User Profile Service unavailable")
    return {"user_id": user_id, "name": "Acme Corp Admin", "tier": "Enterprise"}


async def fetch_inventory(user_id: int) -> dict:
    await asyncio.sleep(0.4)
    return {"active_orders": 12, "warehouse_region": "us-east-1"}


async def fetch_pricing(user_id: int) -> dict:
    await asyncio.sleep(0.2)
    return {"currency": "USD", "bulk_discount": True}


# --- Gateway Aggregator Pattern ---


async def aggregate_user_dashboard(user_id: int) -> DashboardResponse:
    logger.info(f"Starting concurrent dashboard aggregation for user_id={user_id}")
    start_time = time.perf_counter()

    try:
        # Enforce a strict SLA timeout of 0.5 seconds for all downstream calls combined.
        # return_exceptions=True ensures individual failures are captured as exception objects
        # rather than crashing the entire gather batch.
        results = await asyncio.wait_for(
            asyncio.gather(
                fetch_user_profile(user_id),
                fetch_inventory(user_id),
                fetch_pricing(user_id),
                return_exceptions=True,
            ),
            timeout=0.5,
        )
    except asyncio.TimeoutError:
        logger.error(
            f"SLA Breach: Dashboard aggregation timed out for user_id={user_id}"
        )
        return DashboardResponse(user_id=user_id, errors=["Global gateway timeout"])

    profile_res, inventory_res, pricing_res = results
    errors = []

    # Process responses and implement graceful degradation for failed services
    profile = profile_res if not isinstance(profile_res, Exception) else None
    if isinstance(profile_res, Exception):
        errors.append(f"Profile Service Error: {profile_res}")
        logger.warning(f"Degraded experience: {profile_res}")

    inventory = inventory_res if not isinstance(inventory_res, Exception) else None
    if isinstance(inventory_res, Exception):
        errors.append(f"Inventory Service Error: {inventory_res}")
        logger.warning(f"Degraded experience: {inventory_res}")

    pricing = pricing_res if not isinstance(pricing_res, Exception) else None
    if isinstance(pricing_res, Exception):
        errors.append(f"Pricing Service Error: {pricing_res}")
        logger.warning(f"Degraded experience: {pricing_res}")

    duration = time.perf_counter() - start_time
    logger.info(f"Dashboard aggregated in {duration:.4f} seconds")

    return DashboardResponse(
        user_id=user_id,
        profile=profile,
        inventory=inventory,
        pricing=pricing,
        errors=errors,
    )


# --- Execution Simulation ---


async def main():
    print("=== SCENARIO 1: All Microservices Healthy ===")
    healthy_dashboard = await aggregate_user_dashboard(user_id=101)
    print(healthy_dashboard)

    print("\n=== SCENARIO 2: Partial Outage (User 999 Profile Fails) ===")
    degraded_dashboard = await aggregate_user_dashboard(user_id=999)
    print(degraded_dashboard)


if __name__ == "__main__":
    asyncio.run(main())
