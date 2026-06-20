import os
import csv
import glob
from typing import List, Dict, Tuple
from .models import AuditResult


def find_latest_review_csv(output_dir: str) -> str:
    if not os.path.isdir(output_dir):
        return ""
    pattern = os.path.join(output_dir, "复核交接单_*.csv")
    files = glob.glob(pattern)
    if not files:
        return ""
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def load_review_fields(csv_path: str) -> Dict[str, Dict[str, str]]:
    fields: Dict[str, Dict[str, str]] = {}
    if not csv_path or not os.path.isfile(csv_path):
        return fields
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                wb_no = row.get("运单号", "").strip()
                if not wb_no:
                    continue
                status = row.get("复核状态", "").strip()
                remark = row.get("备注", "").strip()
                person = row.get("责任人", "").strip()
                fields[wb_no] = {
                    "review_status": status,
                    "remark": remark,
                    "responsible_person": person
                }
    except Exception:
        pass
    return fields


def apply_review_fields(results: List[AuditResult], fields: Dict[str, Dict[str, str]]) -> int:
    updated = 0
    for r in results:
        if r.waybill_no not in fields:
            if r.is_abnormal and r.review_status != "待复核":
                r.review_status = "待复核"
            continue

        saved = fields[r.waybill_no]

        if saved.get("review_status") in ("已确认", "已放行") and r.is_abnormal:
            r.review_status = saved["review_status"]
            updated += 1
        elif saved.get("review_status") == "正常" and not r.is_abnormal:
            r.review_status = "待复核"
        else:
            if r.is_abnormal:
                r.review_status = "待复核"

        if saved.get("remark"):
            r.remark = saved["remark"]

        if saved.get("responsible_person"):
            r.responsible_person = saved["responsible_person"]

    return updated
