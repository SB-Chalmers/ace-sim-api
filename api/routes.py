"""
api.routes
──────────
  POST /v1/daylight   daylight only (DF, optional DA/sDA)
  POST /v1/energy     energy only (annual totals, monthly balance, hourly loads)
  POST /v1/energy-rc  the same request and result, computed with EPSM RC (ISO 52016-1)
  POST /v1/simulate   both, run at the same time
  POST /v1/grasshopper the same request as a Grasshopper definition (.ghx)
  POST /v1/hbjson     the /v1/energy Honeybee model as a file (.hbjson), not simulated
  POST /v1/hbjson-detailed  the model the /v1/grasshopper file builds, as a .hbjson

Each request is validated, put on a Celery queue, and answered when the
worker is done. Identical requests share one job and abandoned jobs are
cancelled (see api/jobs.py). Nothing is stored: results expire from Redis
shortly after.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from worker import celery_app

from .auth import require_api_key
from .grasshopper import grasshopper_file
from .jobs import submit, wait
from .schemas import (
    DaylightRequest,
    DaylightResult,
    EnergyRequest,
    EnergyResult,
    ErrorResponse,
    GrasshopperRequest,
    SimulateRequest,
    SimulateResult,
)

router = APIRouter(prefix='/v1', dependencies=[Depends(require_api_key)])
_ERRORS = {code: {'model': ErrorResponse} for code in (400, 401, 500, 503, 504)}


def _payload(request) -> dict:
    """Turn the validated request into the plain dict the Celery task receives."""
    data = request.model_dump(mode='json')
    data['room'] = request.room.to_simulation_dict()
    return data


@router.post('/daylight', response_model=DaylightResult, responses=_ERRORS)
async def daylight(body: DaylightRequest, request: Request):
    """Daylight factor per sensor, plus DA/sDA when daylight.run_sda is true."""
    return await wait(*submit(celery_app.daylight, _payload(body)), request)


@router.post('/energy', response_model=EnergyResult, responses=_ERRORS)
async def energy(body: EnergyRequest, request: Request):
    """Annual heating/cooling, monthly heat balance and hourly loads."""
    return await wait(*submit(celery_app.energy, _payload(body)), request)


@router.post('/energy-rc', response_model=EnergyResult, responses=_ERRORS)
async def energy_rc(body: EnergyRequest, request: Request):
    """/v1/energy computed with EPSM RC (ISO 52016-1 hourly model) instead of EnergyPlus.

    Same request and response. RC answers in about 0.1 s against 2 to 4 s; heating
    and cooling follow EnergyPlus closely month by month, with the same direction of
    change for every design input. Window fins are not modelled.
    """
    return await wait(*submit(celery_app.energy_rc, _payload(body)), request)


@router.post('/simulate', response_model=SimulateResult, responses=_ERRORS)
async def simulate(body: SimulateRequest, request: Request):
    """Daylight and energy go to their own queues, so they run in parallel.

    The response waits for both. To show energy as soon as it is ready, call
    /v1/daylight and /v1/energy at the same time instead.
    """
    payload = _payload(body)
    daylight_result, energy_result = await asyncio.gather(
        wait(*submit(celery_app.daylight, payload), request),
        wait(*submit(celery_app.energy, payload), request),
    )
    return {'daylight': daylight_result, 'energy': energy_result}


@router.post('/grasshopper', responses={200: {'content': {'application/xml': {}}}})
async def grasshopper(body: GrasshopperRequest):
    """The request as a Grasshopper definition that rebuilds the same model.

    Open it in Rhino 8 with Ladybug Tools and Foton installed (see
    grasshopper/README.md). Nothing is simulated here.
    """
    payload = _payload(body)
    payload.pop('pack', None)
    return Response(
        grasshopper_file(payload),
        media_type='application/xml',
        headers={'Content-Disposition': 'attachment; filename="heath.ghx"'},
    )


def _hbjson(result: dict) -> Response:
    """The model a hbjson job returned, as a file download."""
    return Response(
        json.dumps(result['model']),
        media_type='application/json',
        headers={'Content-Disposition': 'attachment; filename="heath.hbjson"'},
    )


@router.post('/hbjson', responses={**_ERRORS, 200: {'content': {'application/json': {}}}})
async def hbjson(body: EnergyRequest, request: Request):
    """The Honeybee Model /v1/energy would simulate, as a downloadable .hbjson.

    Same request as /v1/energy. The model (rooms, windows, shades, program,
    EPSM constructions and ideal air) is built on an energy worker and nothing
    is simulated. Open it with HB Model from HBJSON, or Model.from_hbjson.
    """
    return _hbjson(await wait(*submit(celery_app.hbjson, _payload(body)), request))


@router.post('/hbjson-detailed', responses={**_ERRORS, 200: {'content': {'application/json': {}}}})
async def hbjson_detailed(body: EnergyRequest, request: Request):
    """The Honeybee Model the /v1/grasshopper file builds, as a downloadable .hbjson.

    Same request as /v1/energy. One model for daylight and energy, like the
    Grasshopper template: detailed windows with overhangs and fins, the daylight
    floor(s) as zones of their own with sensor grids, EPSM constructions,
    program and ideal air. Nothing is simulated.
    """
    payload = {**_payload(body), 'detailed': True}
    return _hbjson(await wait(*submit(celery_app.hbjson, payload), request))
