"""Review and explicitly approve the PET radionuclide physics dataset."""
from __future__ import annotations
import argparse, json, os, tempfile
from datetime import date
from pathlib import Path
from engine.pet_radionuclide_data import APPROVED, PENDING, load_pet_radionuclide_dataset, records_sha256

class PetRadionuclideApprovalError(ValueError): pass

def confirmation_token(dataset) -> str:
    return f"APPROVE:{dataset.metadata.dataset_id}:{dataset.metadata.revision}"

def review_dataset(path: str | Path) -> str:
    ds=load_pet_radionuclide_dataset(path, allow_unapproved=True)
    lines=["PET RADIONUCLIDE PHYSICS DATASET REVIEW","="*45,
           f"Dataset ID: {ds.metadata.dataset_id}",f"Revision: {ds.metadata.revision}",
           f"Approval status: {ds.metadata.approval_status}",f"Reviewed by: {ds.metadata.reviewed_by}",
           f"Reviewed date: {ds.metadata.reviewed_date}",f"Records SHA-256: {ds.metadata.records_sha256}",""]
    for r in ds.records.values():
        lines += [f"[{r.code}] {r.display_name}",f"  Half-life: {r.half_life_h:g} h",
                  f"  Half-life source: {r.half_life_provenance.source_title}; {r.half_life_provenance.source_value}",
                  f"  Dose-rate constant: {r.dose_rate_constant_uSv_h_per_MBq_at_1m:g} µSv·h⁻¹·MBq⁻¹ at 1 m",
                  f"  Dose-rate source: {r.dose_rate_provenance.source_title}",
                  f"  Derivation: {r.dose_rate_provenance.derivation}",""]
    if ds.metadata.approval_status == PENDING:
        lines += ["PENDING EXPLICIT USER APPROVAL",f"Required confirmation token: {confirmation_token(ds)}"]
    return "\n".join(lines)

def approve_dataset(source: str | Path, output: str | Path, *, approved_by: str, approved_date: str, confirmation: str) -> Path:
    src, out = Path(source).resolve(), Path(output).resolve()
    if src == out: raise PetRadionuclideApprovalError("Approval output must be a separate file.")
    ds=load_pet_radionuclide_dataset(src, allow_unapproved=True)
    if ds.metadata.approval_status != PENDING: raise PetRadionuclideApprovalError("Dataset is not pending approval.")
    if confirmation != confirmation_token(ds): raise PetRadionuclideApprovalError(f"Required token: {confirmation_token(ds)}")
    approver=str(approved_by or '').strip()
    if not approver: raise PetRadionuclideApprovalError("approved_by must not be blank.")
    try: approval_date=date.fromisoformat(approved_date).isoformat()
    except ValueError as exc: raise PetRadionuclideApprovalError("approved_date must use YYYY-MM-DD.") from exc
    payload=json.loads(src.read_text(encoding='utf-8')); digest=records_sha256(payload)
    meta=payload['metadata']; meta.update(approval_status=APPROVED, approved_by=approver, approved_date=approval_date, approved_records_sha256=digest)
    out.parent.mkdir(parents=True, exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=f'.{out.name}.',suffix='.tmp',dir=out.parent)
    with os.fdopen(fd,'w',encoding='utf-8',newline='\n') as h: json.dump(payload,h,indent=2,ensure_ascii=False); h.write('\n')
    os.replace(tmp,out)
    approved=load_pet_radionuclide_dataset(out)
    if approved.metadata.records_sha256 != digest: raise PetRadionuclideApprovalError("Approved record digest mismatch.")
    return out

def main(argv=None) -> int:
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='command',required=True)
    r=sub.add_parser('review'); r.add_argument('dataset',type=Path)
    a=sub.add_parser('approve'); a.add_argument('dataset',type=Path); a.add_argument('--output',type=Path,required=True); a.add_argument('--approved-by',required=True); a.add_argument('--approved-date',required=True); a.add_argument('--confirm',required=True)
    args=p.parse_args(argv)
    try:
        if args.command=='review': print(review_dataset(args.dataset))
        else: print(approve_dataset(args.dataset,args.output,approved_by=args.approved_by,approved_date=args.approved_date,confirmation=args.confirm))
    except Exception as exc: print(f"ERROR: {exc}",file=__import__('sys').stderr); return 2
    return 0
if __name__=='__main__': raise SystemExit(main())
