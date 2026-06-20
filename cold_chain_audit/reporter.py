import os
import csv
from typing import List
from collections import defaultdict
from .models import AuditResult


def print_summary(results: List[AuditResult]) -> None:
    total = len(results)
    abnormal = [r for r in results if r.is_abnormal]
    normal = [r for r in results if not r.is_abnormal]

    print("=" * 60)
    print("  肉类冷链温区稽核结果")
    print("=" * 60)
    print(f"  运单总数: {total} 票")
    print(f"  正常运单: {len(normal)} 票")
    print(f"  异常运单: {len(abnormal)} 票")
    print("-" * 60)

    print("\n【每票匹配记录数】")
    for r in results:
        status = "正常" if not r.is_abnormal else "异常"
        in_transit = r.temp_records_count
        total_matched = r.matched_total_count
        extra = total_matched - in_transit
        match_info = f"途中{in_transit}条"
        if extra > 0:
            match_info += f" + 预冷/卸货{extra}条"
        print(f"  {r.waybill_no}  {r.plate_number}  匹配{total_matched}条 ({match_info})  [{status}]")

    if abnormal:
        print("\n【异常运单列表】")
        for i, r in enumerate(abnormal, 1):
            status_tags = []
            if r.matched_total_count == 0:
                status_tags.append("缺少运输温度数据")
            else:
                if not r.pre_cool_ok:
                    status_tags.append("未预冷")
                if r.has_continuous_overtemp:
                    status_tags.append("连续超温")
                if r.has_post_unload_data:
                    status_tags.append("卸货后计时")
            if not r.has_standard:
                status_tags.append("无客户温区标准")
            tag_str = "、".join(status_tags)

            print(f"  {i}. [{r.waybill_no}] {r.customer} - {r.meat_type}")
            print(f"     车牌: {r.plate_number}  问题: {tag_str}")
            if r.matched_total_count > 0 and r.has_continuous_overtemp and r.overtemp_segments:
                print(f"     实际温度: {r.actual_temp_min:.1f}~{r.actual_temp_max:.1f}℃  "
                      f"目标: {r.target_temp_min:.1f}~{r.target_temp_max:.1f}℃  "
                      f"最高超温: {r.overtemp_max_temp:.1f}℃  "
                      f"累计超温: {r.overtemp_total_minutes:.0f}分钟")
            if r.has_post_unload_data:
                level_text = f" [{r.post_unload_level}]" if r.post_unload_level else ""
                print(f"     卸货后持续记录: {r.post_unload_minutes:.0f}分钟{level_text}  "
                      f"卸货后最高温: {r.post_unload_max_temp:.1f}℃")
    else:
        print("\n  所有运单温度均符合要求，无异常。")

    print("-" * 60)


def generate_audit_files(results: List[AuditResult], output_dir: str) -> List[str]:
    os.makedirs(output_dir, exist_ok=True)
    generated_files = []

    for r in results:
        filename = f"稽核_{r.waybill_no}.txt"
        filepath = os.path.join(output_dir, filename)

        lines = []
        lines.append("=" * 50)
        lines.append("   冷链运输温度稽核摘要")
        lines.append("=" * 50)
        lines.append("")
        lines.append(f"运单号:      {r.waybill_no}")
        lines.append(f"车牌:        {r.plate_number}")
        lines.append(f"客户:        {r.customer}")
        lines.append(f"肉品类型:    {r.meat_type}")
        lines.append(f"装车时间:    {r.load_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"卸货时间:    {r.unload_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"运输时长:    {r.actual_duration_minutes:.0f} 分钟")
        lines.append(f"匹配记录数:  {r.matched_total_count} 条 (途中 {r.temp_records_count} 条)")
        lines.append("")
        lines.append("-" * 50)
        lines.append("【客户温区标准】")
        if r.has_standard:
            lines.append(f"  温度范围:      {r.target_temp_min:.1f}℃ ~ {r.target_temp_max:.1f}℃")
            lines.append(f"  预冷要求:      {'是' if r.pre_cool_required else '否'}")
            lines.append(f"  预冷温度上限:  {r.pre_cool_temp:.1f}℃ (装车前应不高于此温度)")
            lines.append(f"  连续超温阈值:  {r.continuous_overtemp_minutes} 分钟")
        else:
            lines.append(f"  未找到客户温区标准，使用默认值:")
            lines.append(f"  温度范围:      {r.target_temp_min:.1f}℃ ~ {r.target_temp_max:.1f}℃")
            lines.append(f"  预冷要求:      {'是' if r.pre_cool_required else '否'}")
            lines.append(f"  预冷温度上限:  {r.pre_cool_temp:.1f}℃")
            lines.append(f"  连续超温阈值:  {r.continuous_overtemp_minutes} 分钟")
        lines.append("")
        lines.append("-" * 50)
        lines.append("【实际温度】")
        if r.matched_total_count > 0:
            lines.append(f"  最低温度:      {r.actual_temp_min:.1f}℃")
            lines.append(f"  最高温度:      {r.actual_temp_max:.1f}℃")
            lines.append(f"  装车时温度:    {r.pre_cool_temp_at_load:.1f}℃")
        else:
            lines.append(f"  无温度记录数据")
        lines.append("")

        lines.append("-" * 50)
        lines.append("【稽核结果】")
        lines.append(f"  预冷检查:  {'合格' if r.pre_cool_ok else '不合格'}")
        if not r.pre_cool_ok:
            lines.append(f"    → 装车时温度 {r.pre_cool_temp_at_load:.1f}℃，"
                         f"高于要求 {r.pre_cool_temp:.1f}℃")

        lines.append(f"  连续超温:  {'无' if not r.has_continuous_overtemp else '有'}")
        if r.has_continuous_overtemp and r.overtemp_segments:
            lines.append(f"    共 {len(r.overtemp_segments)} 段连续超温，"
                         f"累计 {r.overtemp_total_minutes:.0f} 分钟，"
                         f"最高 {r.overtemp_max_temp:.1f}℃：")
            for i, seg in enumerate(r.overtemp_segments, 1):
                lines.append(
                    f"    第{i}段: {seg.start_time.strftime('%H:%M:%S')} ~ "
                    f"{seg.end_time.strftime('%H:%M:%S')}, "
                    f"持续 {seg.duration_minutes:.0f} 分钟, "
                    f"最高 {seg.max_temp:.1f}℃"
                )

        lines.append(f"  卸货后数据: {'无异常' if not r.has_post_unload_data else '异常'}")
        if r.has_post_unload_data:
            level_text = f"(持续{r.post_unload_level})" if r.post_unload_level else ""
            lines.append(f"    → 卸货后仍有 {r.post_unload_minutes:.0f} 分钟温度记录{level_text}，"
                         f"最高温度 {r.post_unload_max_temp:.1f}℃")

        lines.append("")
        lines.append(f"  总体结论:  {'正常' if not r.is_abnormal else '异常'}")
        lines.append("")

        lines.append("-" * 50)
        lines.append("【建议处理意见】")
        if r.suggestions:
            for i, s in enumerate(r.suggestions, 1):
                lines.append(f"  {i}. {s}")
        else:
            lines.append("  温度记录符合要求，无处理建议。")
        lines.append("")
        lines.append("=" * 50)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        r.summary_file_path = os.path.abspath(filepath)
        generated_files.append(filepath)

    return generated_files


def _get_abnormal_tags(r: AuditResult) -> str:
    tags = []
    if r.matched_total_count == 0:
        tags.append("缺少运输温度数据")
    else:
        if not r.pre_cool_ok:
            tags.append("未预冷")
        if r.has_continuous_overtemp:
            tags.append("连续超温")
        if r.has_post_unload_data:
            tags.append("卸货后计时")
    if not r.has_standard:
        tags.append("无客户温区标准")
    return "、".join(tags)


def generate_daily_report(
    all_results: List[AuditResult],
    output_dir: str
) -> str:
    os.makedirs(output_dir, exist_ok=True)

    date_groups: dict = defaultdict(list)
    for r in all_results:
        d = r.load_time.strftime('%Y-%m-%d')
        date_groups[d].append(r)

    all_report_files = []

    for d, day_results in sorted(date_groups.items()):
        summary_file = os.path.join(output_dir, f"日报_总览_{d}.csv")
        detail_file = os.path.join(output_dir, f"日报_异常明细_{d}.csv")

        key_groups: dict = defaultdict(list)
        for r in day_results:
            key = (r.customer, r.meat_type)
            key_groups[key].append(r)

        summary_rows = []
        for (customer, meat_type), group in sorted(key_groups.items()):
            total_count = len(group)
            abnormal_list = [r for r in group if r.is_abnormal]
            abnormal_count = len(abnormal_list)

            reason_counter: dict = defaultdict(int)
            for r in abnormal_list:
                if r.matched_total_count == 0:
                    reason_counter["缺少运输温度数据"] += 1
                else:
                    if not r.pre_cool_ok:
                        reason_counter["未预冷"] += 1
                    if r.has_continuous_overtemp:
                        reason_counter["连续超温"] += 1
                    if r.has_post_unload_data:
                        reason_counter["卸货后计时"] += 1
                if not r.has_standard:
                    reason_counter["无客户温区标准"] += 1

            if reason_counter:
                sorted_reasons = sorted(reason_counter.items(), key=lambda x: -x[1])
                main_reason = "、".join(
                    f"{reason}({count})" for reason, count in sorted_reasons
                )
            else:
                main_reason = ""

            summary_paths = "; ".join(
                r.summary_file_path for r in group
                if r.summary_file_path
            )

            summary_rows.append({
                "日期": d,
                "客户": customer,
                "肉品类型": meat_type,
                "运单数": total_count,
                "异常数": abnormal_count,
                "主要异常原因": main_reason,
                "摘要文件": summary_paths
            })

        with open(summary_file, 'w', encoding='utf-8-sig', newline='') as f:
            if summary_rows:
                writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
                writer.writeheader()
                writer.writerows(summary_rows)
        all_report_files.append(summary_file)

        abnormal_results = [r for r in day_results if r.is_abnormal]
        detail_rows = []
        for r in abnormal_results:
            overtemp_start = ""
            overtemp_end = ""
            if r.overtemp_segments:
                overtemp_start = r.overtemp_segments[0].start_time.strftime('%H:%M:%S')
                overtemp_end = r.overtemp_segments[-1].end_time.strftime('%H:%M:%S')

            detail_rows.append({
                "日期": d,
                "运单号": r.waybill_no,
                "车牌": r.plate_number,
                "客户": r.customer,
                "肉品类型": r.meat_type,
                "异常类型": _get_abnormal_tags(r),
                "连续超温时长(分钟)": r.overtemp_total_minutes if r.has_continuous_overtemp else "",
                "最高超温(℃)": r.overtemp_max_temp if r.has_continuous_overtemp else "",
                "超温起时": overtemp_start,
                "超温止时": overtemp_end,
                "卸货后持续(分钟)": r.post_unload_minutes if r.has_post_unload_data else "",
                "卸货后档位": r.post_unload_level if r.has_post_unload_data else "",
                "卸货后最高温(℃)": r.post_unload_max_temp if r.has_post_unload_data else "",
                "处理建议": "; ".join(r.suggestions),
                "摘要文件": r.summary_file_path if r.summary_file_path else ""
            })

        with open(detail_file, 'w', encoding='utf-8-sig', newline='') as f:
            if detail_rows:
                writer = csv.DictWriter(f, fieldnames=list(detail_rows[0].keys()))
                writer.writeheader()
                writer.writerows(detail_rows)
        all_report_files.append(detail_file)

    return "\n".join(all_report_files)


def export_review_csv(
    all_results: List[AuditResult],
    output_dir: str
) -> str:
    os.makedirs(output_dir, exist_ok=True)
    dates = sorted(set(r.load_time.strftime('%Y%m%d') for r in all_results))
    date_suffix = "_".join(dates[:3])
    if len(dates) > 3:
        date_suffix += f"_等{len(dates)}日"

    filepath = os.path.join(output_dir, f"复核交接单_{date_suffix}.csv")

    rows = []
    for r in all_results:
        if r.is_abnormal:
            status = r.review_status
        else:
            status = "正常"

        rows.append({
            "运单号": r.waybill_no,
            "车牌": r.plate_number,
            "客户": r.customer,
            "肉品类型": r.meat_type,
            "装车时间": r.load_time.strftime('%Y-%m-%d %H:%M'),
            "卸货时间": r.unload_time.strftime('%Y-%m-%d %H:%M'),
            "稽核结论": "异常" if r.is_abnormal else "正常",
            "异常类型": _get_abnormal_tags(r) if r.is_abnormal else "",
            "处理建议": "; ".join(r.suggestions) if r.suggestions else "",
            "复核状态": status,
            "备注": r.remark,
            "责任人": r.responsible_person,
            "摘要文件路径": r.summary_file_path if r.summary_file_path else ""
        })

    with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    return filepath


def generate_plate_handover_report(
    all_results: List[AuditResult],
    output_dir: str
) -> str:
    os.makedirs(output_dir, exist_ok=True)

    date_groups: dict = defaultdict(list)
    for r in all_results:
        d = r.load_time.strftime('%Y-%m-%d')
        date_groups[d].append(r)

    all_report_files = []

    for d, day_results in sorted(date_groups.items()):
        plate_groups: dict = defaultdict(list)
        for r in day_results:
            plate_groups[r.plate_number].append(r)

        filepath = os.path.join(output_dir, f"车辆交接汇总_{d}.csv")
        rows = []

        for plate, group in sorted(plate_groups.items()):
            total_count = len(group)
            abnormal_list = [r for r in group if r.is_abnormal]
            abnormal_count = len(abnormal_list)

            pending_wbs = [r.waybill_no for r in abnormal_list if r.review_status == "待复核"]
            confirmed_wbs = [r.waybill_no for r in abnormal_list if r.review_status == "已确认"]
            released_wbs = [r.waybill_no for r in abnormal_list if r.review_status == "已放行"]

            normal_count = total_count - abnormal_count
            abnormal_tags_set = set()
            for r in abnormal_list:
                if r.matched_total_count == 0:
                    abnormal_tags_set.add("缺少数据")
                else:
                    if not r.pre_cool_ok:
                        abnormal_tags_set.add("未预冷")
                    if r.has_continuous_overtemp:
                        abnormal_tags_set.add("连续超温")
                    if r.has_post_unload_data:
                        abnormal_tags_set.add("卸货后计时")
                if not r.has_standard:
                    abnormal_tags_set.add("无标准")

            pending_remarks = []
            for r in abnormal_list:
                if r.review_status == "待复核" and r.remark:
                    pending_remarks.append(f"{r.waybill_no}: {r.remark}")

            rows.append({
                "日期": d,
                "车牌": plate,
                "运单数": total_count,
                "正常数": normal_count,
                "异常数": abnormal_count,
                "主要异常类型": "、".join(sorted(abnormal_tags_set)),
                "待复核运单": "; ".join(pending_wbs),
                "待复核数": len(pending_wbs),
                "待复核备注": "; ".join(pending_remarks),
                "已确认运单": "; ".join(confirmed_wbs),
                "已确认数": len(confirmed_wbs),
                "已放行运单": "; ".join(released_wbs),
                "已放行数": len(released_wbs),
                "全部运单": "; ".join(r.waybill_no for r in group)
            })

        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

        all_report_files.append(filepath)

    return "\n".join(all_report_files)


def print_plate_summary(results: List[AuditResult]) -> None:
    date_groups: dict = defaultdict(list)
    for r in results:
        d = r.load_time.strftime('%Y-%m-%d')
        date_groups[d].append(r)

    print("\n【车辆交接汇总】")
    for d, day_results in sorted(date_groups.items()):
        plate_groups: dict = defaultdict(list)
        for r in day_results:
            plate_groups[r.plate_number].append(r)

        print(f"  日期: {d}")
        for plate, group in sorted(plate_groups.items()):
            total = len(group)
            abn = sum(1 for r in group if r.is_abnormal)
            pending = sum(1 for r in group if r.is_abnormal and r.review_status == "待复核")
            conf = sum(1 for r in group if r.is_abnormal and r.review_status == "已确认")
            rel = sum(1 for r in group if r.is_abnormal and r.review_status == "已放行")
            normal = total - abn
            print(f"    {plate}: {total}票(正常{normal},异常{abn}) "
                  f"待复核{pending} 已确认{conf} 已放行{rel}")

            if pending:
                pending_wbs = [r.waybill_no for r in group if r.is_abnormal and r.review_status == "待复核"]
                remark_wbs = [r for r in group if r.is_abnormal and r.review_status == "待复核" and r.remark]
                print(f"      待复核: {', '.join(pending_wbs)}")
                if remark_wbs:
                    for rr in remark_wbs:
                        print(f"        {rr.waybill_no} 备注: {rr.remark}")
    print("-" * 60)


def generate_vehicle_review(
    all_results: List[AuditResult],
    output_dir: str
) -> str:
    os.makedirs(output_dir, exist_ok=True)

    date_groups: dict = defaultdict(list)
    for r in all_results:
        d = r.load_time.strftime('%Y-%m-%d')
        date_groups[d].append(r)

    all_report_files = []

    for d, day_results in sorted(date_groups.items()):
        plate_groups: dict = defaultdict(list)
        for r in day_results:
            plate_groups[r.plate_number].append(r)

        for plate, group in sorted(plate_groups.items()):
            group_sorted = sorted(group, key=lambda r: r.load_time)
            filepath = os.path.join(output_dir, f"车辆复盘_{d}_{plate}.csv")

            rows = []
            first_load = group_sorted[0].load_time
            last_unload = group_sorted[-1].unload_time

            for seq, r in enumerate(group_sorted, 1):
                abnormal_tag = _get_abnormal_tags(r) if r.is_abnormal else ""
                review_st = r.review_status if r.is_abnormal else "正常"
                post_info = ""
                if r.has_post_unload_data:
                    lv = f" [{r.post_unload_level}]" if r.post_unload_level else ""
                    post_info = f"{r.post_unload_minutes:.0f}分钟{lv} 最高{r.post_unload_max_temp:.1f}℃"

                rows.append({
                    "序号": seq,
                    "运单号": r.waybill_no,
                    "客户": r.customer,
                    "肉品类型": r.meat_type,
                    "装车时间": r.load_time.strftime('%H:%M'),
                    "卸货时间": r.unload_time.strftime('%H:%M'),
                    "运输时长(分钟)": r.actual_duration_minutes,
                    "匹配记录数": r.matched_total_count,
                    "途中记录数": r.temp_records_count,
                    "实际温度范围": f"{r.actual_temp_min:.1f}~{r.actual_temp_max:.1f}℃" if r.matched_total_count > 0 else "无数据",
                    "目标温度范围": f"{r.target_temp_min:.1f}~{r.target_temp_max:.1f}℃",
                    "稽核结论": "异常" if r.is_abnormal else "正常",
                    "异常节点": abnormal_tag,
                    "连续超温(分钟)": r.overtemp_total_minutes if r.has_continuous_overtemp else "",
                    "卸货后延续": post_info,
                    "复核状态": review_st,
                    "备注": r.remark,
                    "责任人": r.responsible_person,
                    "摘要文件": r.summary_file_path if r.summary_file_path else ""
                })

            with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
                if rows:
                    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                    writer.writeheader()
                    writer.writerows(rows)

            all_report_files.append(filepath)

    return "\n".join(all_report_files)


def print_vehicle_review_summary(results: List[AuditResult]) -> None:
    date_groups: dict = defaultdict(list)
    for r in results:
        d = r.load_time.strftime('%Y-%m-%d')
        date_groups[d].append(r)

    print("\n【车辆日终复盘】")
    for d, day_results in sorted(date_groups.items()):
        plate_groups: dict = defaultdict(list)
        for r in day_results:
            plate_groups[r.plate_number].append(r)

        print(f"  日期: {d}")
        for plate, group in sorted(plate_groups.items()):
            group_sorted = sorted(group, key=lambda r: r.load_time)
            first = group_sorted[0].load_time.strftime('%H:%M')
            last = group_sorted[-1].unload_time.strftime('%H:%M')
            total = len(group_sorted)
            abn = sum(1 for r in group_sorted if r.is_abnormal)
            pending = sum(1 for r in group_sorted if r.is_abnormal and r.review_status == "待复核")
            print(f"    {plate}: {first}~{last}  {total}票 异常{abn} 待复核{pending}")

            for seq, r in enumerate(group_sorted, 1):
                tag = ""
                if r.is_abnormal:
                    tag = f" ⚠ {_get_abnormal_tags(r)}"
                st = r.review_status if r.is_abnormal else "正常"
                print(f"      {seq}. {r.waybill_no} "
                      f"{r.load_time.strftime('%H:%M')}→{r.unload_time.strftime('%H:%M')} "
                      f"匹配{r.matched_total_count}条 "
                      f"[{st}]{tag}")
    print("-" * 60)


def generate_trend_report(
    all_results: List[AuditResult],
    output_dir: str
) -> str:
    os.makedirs(output_dir, exist_ok=True)

    date_groups: dict = defaultdict(list)
    for r in all_results:
        d = r.load_time.strftime('%Y-%m-%d')
        date_groups[d].append(r)

    all_report_files = []

    for d, day_results in sorted(date_groups.items()):
        filepath = os.path.join(output_dir, f"异常趋势_{d}.csv")

        key_type_groups: dict = defaultdict(list)
        for r in day_results:
            if not r.is_abnormal:
                continue
            tags = _get_abnormal_tags(r).split("、")
            for tag in tags:
                tag = tag.strip()
                if tag:
                    key = (r.customer, r.meat_type, tag)
                    key_type_groups[key].append(r)

        rows = []
        for key in sorted(key_type_groups.keys()):
            customer, meat_type, tag = key
            actual_group = key_type_groups[key]
            plates = sorted(set(r.plate_number for r in actual_group))
            wb_nos = [r.waybill_no for r in actual_group]
            remarks = [f"{r.waybill_no}:{r.remark}" for r in actual_group if r.remark]

            rows.append({
                "日期": d,
                "客户": customer,
                "肉品类型": meat_type,
                "异常类型": tag,
                "运单数": len(actual_group),
                "涉及车牌": "、".join(plates),
                "涉及运单": "; ".join(wb_nos),
                "备注摘要": "; ".join(remarks) if remarks else ""
            })

        rows.sort(key=lambda x: -x["运单数"])

        with open(filepath, 'w', encoding='utf-8-sig', newline='') as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)

        all_report_files.append(filepath)

    return "\n".join(all_report_files)

