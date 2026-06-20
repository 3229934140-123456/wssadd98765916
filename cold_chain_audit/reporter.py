import os
from typing import List
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

    if abnormal:
        print("\n【异常运单列表】")
        for i, r in enumerate(abnormal, 1):
            status_tags = []
            if not r.pre_cool_ok:
                status_tags.append("未预冷")
            if r.has_continuous_overtemp:
                status_tags.append("连续超温")
            if r.has_post_unload_data:
                status_tags.append("卸货后计时")
            tag_str = "、".join(status_tags)

            print(f"  {i}. [{r.waybill_no}] {r.customer} - {r.meat_type}")
            print(f"     车牌: {r.plate_number}  问题: {tag_str}")
            if r.has_continuous_overtemp and r.overtemp_segments:
                max_ot = max(s.max_temp for s in r.overtemp_segments)
                print(f"     实际温度: {r.actual_temp_min:.1f}~{r.actual_temp_max:.1f}℃  "
                      f"目标: {r.target_temp_min:.1f}~{r.target_temp_max:.1f}℃  "
                      f"最高超温: {max_ot:.1f}℃")
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
        lines.append(f"")
        lines.append(f"运单号:      {r.waybill_no}")
        lines.append(f"车牌:        {r.plate_number}")
        lines.append(f"客户:        {r.customer}")
        lines.append(f"肉品类型:    {r.meat_type}")
        lines.append(f"装车时间:    {r.load_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"卸货时间:    {r.unload_time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"运输时长:    {r.actual_duration_minutes:.0f} 分钟")
        lines.append(f"温度记录数:  {r.temp_records_count} 条")
        lines.append(f"")
        lines.append("-" * 50)
        lines.append("【目标温区】")
        lines.append(f"  温度范围:  {r.target_temp_min:.1f}℃ ~ {r.target_temp_max:.1f}℃")
        lines.append(f"  预冷要求:  {'是' if r.target_temp_min < 0 else '否'} "
                     f"(装车前温度不高于 {r.target_temp_max:.1f}℃)")
        lines.append(f"  连续超温判定阈值: {10} 分钟")
        lines.append("")
        lines.append("-" * 50)
        lines.append("【实际温度】")
        lines.append(f"  最低温度:  {r.actual_temp_min:.1f}℃")
        lines.append(f"  最高温度:  {r.actual_temp_max:.1f}℃")
        lines.append(f"  装车时温度: {r.pre_cool_temp_at_load:.1f}℃")
        lines.append("")

        lines.append("-" * 50)
        lines.append("【稽核结果】")
        lines.append(f"  预冷检查:  {'合格' if r.pre_cool_ok else '不合格'}")
        if not r.pre_cool_ok:
            lines.append(f"    → 装车时温度 {r.pre_cool_temp_at_load:.1f}℃，"
                         f"高于要求 {r.target_temp_max:.1f}℃")

        lines.append(f"  连续超温:  {'无' if not r.has_continuous_overtemp else '有'}")
        if r.has_continuous_overtemp and r.overtemp_segments:
            lines.append(f"    共 {len(r.overtemp_segments)} 段连续超温：")
            for i, seg in enumerate(r.overtemp_segments, 1):
                lines.append(
                    f"    第{i}段: {seg.start_time.strftime('%H:%M:%S')} ~ "
                    f"{seg.end_time.strftime('%H:%M:%S')}, "
                    f"持续 {seg.duration_minutes:.0f} 分钟, "
                    f"最高 {seg.max_temp:.1f}℃"
                )

        lines.append(f"  卸货后数据: {'无异常' if not r.has_post_unload_data else '异常'}")
        if r.has_post_unload_data:
            lines.append(f"    → 卸货后仍有 {r.post_unload_minutes:.0f} 分钟温度数据")

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

        generated_files.append(filepath)

    return generated_files
