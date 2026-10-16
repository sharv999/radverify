from reports.report_generator import _source_design_basis_table


def _cell_text(cell):
    if hasattr(cell, "getPlainText"):
        return cell.getPlainText()
    return str(cell)


def test_ct_source_design_basis_includes_scanner_model_name():
    room = {
        "modality": "CT",
        "sources": [
            {
                "name": "Secondary scatter source diagnostic",
                "source_type": "ct_scatter",
                "radiation_type": "xray_140kvp",
                "params": {
                    "scanner_vendor": "Canon",
                    "scanner_model": "Canon Aquilion Exceed LB",
                    "scans_per_week": 60,
                    "workload_mAs_per_scan": 630,
                    "ksec_mGy_per_100mAs_at_1m": 0.005,
                    "scanner_kvp": 140,
                },
            }
        ],
    }

    table = _source_design_basis_table(room)
    rows = [[_cell_text(cell) for cell in row] for row in table._cellvalues]

    assert ["Scanner", "Canon Aquilion Exceed LB"] in rows
