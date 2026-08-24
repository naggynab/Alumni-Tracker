"""CSV row builders shared by HTTP and scheduled department exports."""

from django.http import Http404


def export_rows(report, breakdown):
    if breakdown == "full":
        rows = [("section", "label", "total", "share", "detail", "detail_share")]
        rows.append(("headline", "total alumni", report["total"], "", "", ""))
        rows.append(("headline", "registered accounts", report["registered"], "", "", ""))
        rows.append(("headline", "living in Nepal", report["in_nepal"], report["in_nepal_percent"], "", ""))
        rows.append(("headline", "living abroad", report["abroad"], report["abroad_percent"], "", ""))
        for section, key in (
            ("batches", "by_batch"),
            ("countries", "by_country"),
            ("cities", "by_city"),
            ("districts", "by_district"),
            ("programs", "by_field"),
            ("employment", "by_employment"),
            ("employers", "by_employer"),
            ("study countries", "by_study_country"),
            ("study institutions", "by_study_institution"),
        ):
            for row in report[key]:
                rows.append(
                    (
                        section,
                        row["label"],
                        row["total"],
                        row.get("share", ""),
                        row.get("abroad", ""),
                        row.get("abroad_share", ""),
                    )
                )
        for row in report["adoption"]:
            rows.append(
                (
                    "adoption",
                    row["batch"],
                    row["total"],
                    row["claimed_share"],
                    row["claimed"],
                    row["unclaimed"],
                )
            )
        for row in report["missing_data"]:
            rows.append(("missing data", row["label"], row["total"], row["share"], "", ""))
        return rows

    mapping = {
        "country": ("label", "total", "share"),
        "city": ("label", "total", "share"),
        "district": ("label", "total", "share"),
        "field": ("label", "total", "share", "in_nepal", "abroad", "unknown"),
        "employment": ("label", "total", "share"),
        "employer": ("label", "total", "share"),
        "study_country": ("label", "total", "share"),
        "study_institution": ("label", "total", "share"),
        "batch": ("label", "total", "abroad", "abroad_share"),
        "adoption": ("batch", "total", "claimed", "unclaimed", "claimed_share"),
        "missing_data": ("label", "total", "share"),
    }
    report_keys = {
        "country": "by_country",
        "city": "by_city",
        "district": "by_district",
        "field": "by_field",
        "employment": "by_employment",
        "employer": "by_employer",
        "study_country": "by_study_country",
        "study_institution": "by_study_institution",
        "batch": "by_batch",
        "adoption": "adoption",
        "missing_data": "missing_data",
    }
    if breakdown not in mapping:
        raise Http404("Unknown report export.")
    columns = mapping[breakdown]
    return [columns] + [
        tuple(row.get(column, "") for column in columns)
        for row in report[report_keys[breakdown]]
    ]
