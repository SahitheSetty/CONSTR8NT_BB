from app.service import investigate_target
from backend.person2.path_analysis import compare_paths


def investigate_and_compare(previous_data, target):
    current_result = investigate_target(target)

    current_data = current_result.model_dump()

    return compare_paths(previous_data, current_data)