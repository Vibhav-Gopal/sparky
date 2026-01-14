# schemas.py
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Tuple


ALLOWED_MOTIONS = {"slow_zoom", "pan_left", "pan_right", "static"}


class PatchError(Exception):
    pass


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def merge_video_spec_with_patch(
    spec: Dict[str, Any],
    patch: Dict[str, Any],
    *,
    strict: bool = True,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Merge a YAML patch into the main video spec.

    Returns:
        (new_spec, summary)

    Patch format expected:
    patch = {
      "scenes": {
        "s2": {
          "duration": -1.0,
          "text": "replacement text",
          "visual": {
            "prompt_adjustment": "less detail",
            "motion": "pan_right"
          }
        }
      }
    }

    Behavior:
    - duration: treated as RELATIVE delta (added to existing)
    - text: FULL replacement text
    - prompt_adjustment: appended to existing prompt with ", "
    - motion: replaced if valid, ignored if null/None

    strict=True will raise on unknown scene IDs or invalid schema.
    strict=False will ignore unknown scenes/fields.
    """

    new_spec = deepcopy(spec)
    summary = {
        "changed_scenes": [],
        "ignored": [],
        "errors": [],
    }

    if not patch or patch == {"scenes": {}}:
        return new_spec, summary
    
    if "scenes" not in patch:
        
        msg = "Patch missing top-level key 'scenes'."
        if strict:
            raise PatchError(msg)
        summary["ignored"].append(msg)
        return new_spec, summary

    if not isinstance(patch["scenes"], dict):
        msg = "Patch 'scenes' must be a mapping/dict of scene_id -> edits."
        if strict:
            raise PatchError(msg)
        summary["ignored"].append(msg)
        return new_spec, summary

    # Build scene lookup
    if "scenes" not in new_spec or not isinstance(new_spec["scenes"], list):
        raise PatchError("Spec must contain 'scenes' as a list.")

    scene_index = {s.get("id"): i for i, s in enumerate(new_spec["scenes"]) if isinstance(s, dict)}
    valid_scene_ids = set(scene_index.keys())

    for scene_id, edits in patch["scenes"].items():
        if scene_id not in valid_scene_ids:
            msg = f"Unknown scene_id '{scene_id}' in patch."
            if strict:
                raise PatchError(msg)
            summary["ignored"].append(msg)
            continue

        if not isinstance(edits, dict):
            msg = f"Edits for scene '{scene_id}' must be a dict."
            if strict:
                raise PatchError(msg)
            summary["ignored"].append(msg)
            continue

        s = new_spec["scenes"][scene_index[scene_id]]
        changed_anything = False

        # ---- duration delta ----
        if "duration" in edits:
            delta = edits["duration"]
            if delta is None:
                summary["ignored"].append(f"Ignored duration=null for {scene_id}")
            elif not _is_number(delta):
                msg = f"Scene '{scene_id}': duration must be a number delta (+/-). Got: {delta!r}"
                if strict:
                    raise PatchError(msg)
                summary["errors"].append(msg)
            else:
                old = float(s.get("duration", 0.0))
                new = old + float(delta)
                if new <= 0:
                    msg = f"Scene '{scene_id}': duration became <= 0 after patch ({new})."
                    if strict:
                        raise PatchError(msg)
                    summary["errors"].append(msg)
                else:
                    s["duration"] = round(new, 3)
                    changed_anything = True

        # ---- text replacement ----
        if "text" in edits:
            new_text = edits["text"]
            if new_text is None:
                summary["ignored"].append(f"Ignored text=null for {scene_id}")
            elif not isinstance(new_text, str):
                msg = f"Scene '{scene_id}': text must be a string. Got: {type(new_text).__name__}"
                if strict:
                    raise PatchError(msg)
                summary["errors"].append(msg)
            else:
                # Full replacement (not "adjustment")
                s["text"] = new_text.strip()
                changed_anything = True

        # ---- visual edits ----
        if "visual" in edits:
            v_edits = edits["visual"]
            if v_edits is None:
                summary["ignored"].append(f"Ignored visual=null for {scene_id}")
            elif not isinstance(v_edits, dict):
                msg = f"Scene '{scene_id}': visual must be a dict."
                if strict:
                    raise PatchError(msg)
                summary["errors"].append(msg)
            else:
                if "visual" not in s or not isinstance(s["visual"], dict):
                    s["visual"] = {}

                # prompt_adjustment -> append to prompt
                if "prompt_adjustment" in v_edits:
                    adj = v_edits["prompt_adjustment"]
                    if adj is None:
                        summary["ignored"].append(f"Ignored prompt_adjustment=null for {scene_id}")
                    elif not isinstance(adj, str):
                        msg = f"Scene '{scene_id}': prompt_adjustment must be a string."
                        if strict:
                            raise PatchError(msg)
                        summary["errors"].append(msg)
                    else:
                        base_prompt = s["visual"].get("prompt", "").strip()
                        adj_clean = adj.strip()

                        if base_prompt and adj_clean:
                            s["visual"]["prompt"] = f"{base_prompt}, {adj_clean}"
                        elif adj_clean:
                            s["visual"]["prompt"] = adj_clean
                        changed_anything = True

                # motion -> replace if valid (ignore null)
                if "motion" in v_edits:
                    motion = v_edits["motion"]
                    if motion is None:
                        summary["ignored"].append(f"Ignored motion=null for {scene_id}")
                    elif not isinstance(motion, str):
                        msg = f"Scene '{scene_id}': motion must be a string."
                        if strict:
                            raise PatchError(msg)
                        summary["errors"].append(msg)
                    else:
                        motion_clean = motion.strip()
                        if motion_clean not in ALLOWED_MOTIONS:
                            msg = (
                                f"Scene '{scene_id}': motion '{motion_clean}' invalid. "
                                f"Allowed: {sorted(ALLOWED_MOTIONS)}"
                            )
                            if strict:
                                raise PatchError(msg)
                            summary["errors"].append(msg)
                        else:
                            s["visual"]["motion"] = motion_clean
                            changed_anything = True

                # disallow full prompt replacement via "prompt"
                if "prompt" in v_edits:
                    msg = f"Scene '{scene_id}': patch attempted to set 'visual.prompt'. Use prompt_adjustment only."
                    if strict:
                        raise PatchError(msg)
                    summary["ignored"].append(msg)

        if changed_anything:
            summary["changed_scenes"].append(scene_id)

    return new_spec, summary
if __name__ == "__main__":
    import yaml
    with open("video.yaml", "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    with open("build/video_patch.yaml", "r", encoding="utf-8") as f:
        patch = yaml.safe_load(f)


    new_spec, summary = merge_video_spec_with_patch(spec, patch, strict=True)
    yaml.safe_dump(new_spec, open("build/video_test.yaml", "w"), sort_keys=False, allow_unicode=True, width=100000)

    print("Summary:")
    print(summary)