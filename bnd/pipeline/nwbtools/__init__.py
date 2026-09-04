import json
from functools import lru_cache
from pathlib import Path

POSE_CONFIG_PATH = Path(__file__).parent / "anipose_keypoints.json"


@lru_cache(maxsize=1)
def _load_pose_config() -> dict:
    """
    Loads the anipose keypoint, angle and 2D camera definitions shipped with the package.

    The file is data rather than logic: it describes the pose estimation model and the
    camera rig, so it changes independently of the conversion code.
    """
    try:
        with open(POSE_CONFIG_PATH, "r") as file:
            pose_config = json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Pose configuration file not found: {POSE_CONFIG_PATH}"
        ) from None
    except json.JSONDecodeError as e:
        raise ValueError(f"Could not parse {POSE_CONFIG_PATH}: {e}") from None

    known_keypoints = set(pose_config["keypoint_names"])
    for section in ("angles", "cameras_2d"):
        for name, keypoints in pose_config[section].items():
            unknown = [kp for kp in keypoints if kp not in known_keypoints]
            if unknown:
                raise ValueError(
                    f"{POSE_CONFIG_PATH}: {section}.{name} refers to keypoints that are "
                    f"not in `keypoint_names`: {unknown}"
                )

    return pose_config
