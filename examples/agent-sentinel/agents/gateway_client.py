"""Gateway client — shared helpers for workers and sentinels.

Workers use gateway_request() to execute tools through the Action Gateway.
Sentinels use gateway_query() to query the gateway's tamper-proof ledger.

Both fail-closed: if the gateway is unreachable, the default is denial/empty.
"""

import asyncio
from uuid import uuid4

from bedsheet.sense import Signal


async def gateway_request(
    agent, action: str, params: dict, timeout: float = 10.0
) -> dict:
    """Request tool execution through the Action Gateway.

    Returns dict with keys: verdict, result, reason, rate.
    Fails closed on timeout (returns denial).
    """
    correlation_id = uuid4().hex[:12]

    loop = asyncio.get_running_loop()
    future: asyncio.Future[Signal] = loop.create_future()
    agent._pending_requests[correlation_id] = future

    signal = Signal(
        kind="request",
        sender=agent.name,
        target="action-gateway",
        correlation_id=correlation_id,
        payload={
            "type": "action_request",
            "action": action,
            "params": params,
        },
    )
    await agent.send_to("action-gateway", signal)

    try:
        response_signal = await asyncio.wait_for(future, timeout=timeout)
        return response_signal.payload
    except asyncio.TimeoutError:
        return {
            "verdict": "denied",
            "result": "",
            "reason": "gateway_unreachable",
            "rate": 0,
        }
    finally:
        agent._pending_requests.pop(correlation_id, None)


async def gateway_query(
    agent, query_type: str, params: dict, timeout: float = 10.0
) -> dict:
    """Query the gateway ledger (rate stats, agent logs).

    Returns the gateway's response payload, or empty dict on timeout.
    """
    correlation_id = uuid4().hex[:12]

    loop = asyncio.get_running_loop()
    future: asyncio.Future[Signal] = loop.create_future()
    agent._pending_requests[correlation_id] = future

    payload = {"type": query_type}
    payload.update(params)

    signal = Signal(
        kind="request",
        sender=agent.name,
        target="action-gateway",
        correlation_id=correlation_id,
        payload=payload,
    )
    await agent.send_to("action-gateway", signal)

    try:
        response_signal = await asyncio.wait_for(future, timeout=timeout)
        return response_signal.payload
    except asyncio.TimeoutError:
        return {}
    finally:
        agent._pending_requests.pop(correlation_id, None)
