"""SPECT Step 21 canonical practical request/replay regression guards."""
from __future__ import annotations
import json
from pathlib import Path
import pytest
from modalities.registry import production_modality_names, source_calculation_blocked_reason
from modalities.spect import SPECT_CALCULATION_BLOCK_REASON
from engine.spect_calculation_request_contract import (
    SPECT_CALCULATION_REQUEST_SCHEMA, SPECT_CALCULATION_REQUEST_VERSION,
    SPECT_CALCULATION_RESULT_SCHEMA, SpectCalculationRequestError,
    current_spect_calculation_physics_freeze, load_and_replay_spect_calculation_request,
    spect_calculation_request_from_dict, spect_calculation_request_to_dict,
)
from tools.spect_cli_regression import load_manifest, run_manifest

ROOT=Path(__file__).resolve().parents[1]
FIX=ROOT/'tests'/'fixtures'/'spect_requests'
STANDARD=FIX/'spect-tc99m-standard-two-barrier-v1.json'
CAUTION=FIX/'spect-tc99m-low-transmission-caution-v1.json'
MANIFEST=FIX/'spect_cli_regression_manifest.json'

def test_step21_request_is_canonical_and_pins_step20_freeze():
    raw=json.loads(STANDARD.read_text(encoding='utf-8'))
    req=spect_calculation_request_from_dict(raw)
    assert raw == spect_calculation_request_to_dict(req)
    assert raw['schema']==SPECT_CALCULATION_REQUEST_SCHEMA
    assert raw['schema_version']==SPECT_CALCULATION_REQUEST_VERSION
    assert raw['production_eligible'] is False
    assert raw['physics_freeze']==current_spect_calculation_physics_freeze()

def test_step21_replay_is_deterministic_and_nonproduction():
    a=load_and_replay_spect_calculation_request(STANDARD)
    b=load_and_replay_spect_calculation_request(STANDARD)
    assert a.payload==b.payload
    assert a.payload['schema']==SPECT_CALCULATION_RESULT_SCHEMA
    assert a.payload['production_eligible'] is False
    assert a.payload['replay_verified'] is True
    assert len(a.payload['request_sha256'])==64
    assert [r.material_key for r in a.schedule.rows]==['lead','concrete_2300kg_m3']

def test_step21_caution_fixture_freezes_scope_warning():
    r=load_and_replay_spect_calculation_request(CAUTION)
    assert r.schedule.requires_room_scatter_review is True
    assert r.schedule.contains_source_model_extrapolation is False

def test_step21_request_rejects_changed_physics_freeze_even_if_otherwise_valid():
    raw=json.loads(STANDARD.read_text(encoding='utf-8'))
    raw['physics_freeze']['practical_transmission']['revision']='changed'
    with pytest.raises(SpectCalculationRequestError, match='physics freeze'):
        spect_calculation_request_from_dict(raw)

def test_step21_request_rejects_extra_fields_and_noncanonical_numbers():
    raw=json.loads(STANDARD.read_text(encoding='utf-8'))
    raw['unexpected']=True
    with pytest.raises(SpectCalculationRequestError, match='missing or unexpected'):
        spect_calculation_request_from_dict(raw)

def test_step21_manifest_is_pinned_to_two_replay_fixtures():
    m=load_manifest(MANIFEST)
    assert m['physics_freeze_id']=='spect-physics-step20-2026-08-23'
    assert [x['fixture_id'] for x in m['fixtures']]==[
        'spect-tc99m-standard-two-barrier-v1','spect-tc99m-low-transmission-caution-v1'
    ]

def test_step21_manifest_replay_passes_with_expected_digests():
    _,cases=run_manifest(MANIFEST)
    assert len(cases)==2
    assert cases[0][2]=='c435d732b516b283b30dc2db3991f9c370543a4134ed886b5f3ca013ce112f85'
    assert cases[1][2]=='0d5c500b60db7c2819bb8469e5a7683f883c383ac9840223d404cdbe8fa518da'

def test_step21_manifest_detects_output_regression(tmp_path):
    raw=json.loads(MANIFEST.read_text(encoding='utf-8'))
    raw['fixtures'][0]['expected_output_sha256']='0'*64
    p=tmp_path/'manifest.json'; p.write_text(json.dumps(raw),encoding='utf-8')
    from tools.spect_cli_regression import SpectCliRegressionError
    with pytest.raises(SpectCliRegressionError, match='output digest mismatch'):
        run_manifest(p)

def test_step21_does_not_enable_production_or_leak_into_reports():
    assert 'SPECT' in production_modality_names()
    assert source_calculation_blocked_reason('spect_patient')==SPECT_CALCULATION_BLOCK_REASON
    forbidden=('spect_calculation_request_contract','spect_cli_regression','radshield_spect_practical_calculation_request_v1')
    paths=[ROOT/'app.py',ROOT/'engine'/'shielding_engine.py']; paths.extend((ROOT/'reports').glob('*.py'))
    for p in paths:
        text=p.read_text(encoding='utf-8')
        for token in forbidden: assert token not in text, f'{token} leaked into {p}'
