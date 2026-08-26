#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
R3 = ROOT / "reports/article_experiments/nh_r3_end_to_end_resource_benchmark"

PARENT = "18f6c02c351c7c257c5f108f3dafb972095eeb14"
BRANCH = "paper/nh-r3-end-to-end-resource-benchmark-20260820T193919Z"

CONTRACT = R3 / "config/r3_e8_pre_bundle_static_completion_contract.json"
SNAPSHOT = R3 / "results/e8_pre_bundle_static_completion_snapshot.json"

EXPECTED_E7_BLOBS = {
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_e7_xmla_inference_engine_static_contract.json":
        "caea2ca1f4d704d6c76a5e16d4ecf670094505b4",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/config/r3_e7_xmla_inference_synthetic_test_vectors.json":
        "cce56566b21d268d18c365ab6c3f6d001d6c21c4",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/implementation/r3_e7_xmla_inference_engine.py":
        "8a77d336d66ea292dfb728ce55beb607f65128db",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/implementation/verify_r3_e7_xmla_inference_synthetic.py":
        "85110656e469d97babf6a4b377d44c5705730289",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/results/e7_static_verifier_recovery.json":
        "2b8a16e058308ed209e1c4214980408f582a2c4a",
    "reports/article_experiments/nh_r3_end_to_end_resource_benchmark/results/e7_xmla_inference_synthetic_test_receipt.json":
        "d71055e71cc810f2698c69e538fdd3021a617b90",
}

EXPECTED_LINEAGE = [
    "b88cc576ec547ebbb71edee181dddda866cf3a33",
    "e93641209b70605237931bf962bc83ac0dc81a48",
    "c7f727db7b5c67c161e6357bb2dde4f3cf313d62",
    "918ea6d4eb3f0a517b637dcef6c033f12a724d01",
    "43c0e5855909b045fbc1e0395d697a9794f02c10",
    "e34ba8e6e0c1267974305053557c6a28acfe2c11",
    "effd3a0677bc943f51faf87f4808743136ba027b",
    "45dc105e6e9c1ef800323af2a78987a2b8ddcf11",
    PARENT,
]


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_lineage() -> None:
    if git("branch", "--show-current") != BRANCH:
        raise RuntimeError("wrong branch")
    if git("rev-parse", PARENT + "^{commit}") != PARENT:
        raise RuntimeError("E7 parent missing")
    for commit in EXPECTED_LINEAGE:
        subprocess.run(
            ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", commit, "HEAD"],
            check=True,
        )
    for rel, expected in EXPECTED_E7_BLOBS.items():
        actual = git("rev-parse", "HEAD:" + rel)
        if actual != expected:
            raise RuntimeError("E7 authority changed: " + rel + " -> " + actual)


def verify_e7() -> None:
    subprocess.run(
        [
            "python",
            str(R3 / "implementation/verify_r3_e7_xmla_inference_synthetic.py"),
        ],
        check=True,
    )


def verify_contract() -> None:
    c = load(CONTRACT)
    s = load(SNAPSHOT)

    if c["parent_e7_head"] != PARENT:
        raise RuntimeError("E8 parent binding changed")
    if c["next_experimental_state"] != "BLOCKED_WAITING_FOR_VERIFIED_BUNDLE_RECOVERY_AND_NEW_HOST_E2_READ_ONLY_REVALIDATION":
        raise RuntimeError("E8 blocked experimental state changed")

    completed = c["static_experimental_completion"]
    expected_true = [
        "bundle_independent_runtime_design_complete",
        "pinned_emondrian_inputs_complete",
        "isolated_runtime_overlay_static_plan_complete",
        "executor_receipt_schema_static_complete",
        "inference_protocol_static_complete",
        "inference_engine_synthetic_tests_complete",
    ]
    for key in expected_true:
        if completed[key] is not True:
            raise RuntimeError("static completion regressed: " + key)

    expected_false = [
        "runtime_materialization_complete",
        "xmla_mechanical_runtime_validation_complete",
        "xmla_measured_execution_complete",
        "xmla_real_inference_complete",
        "r3_f_cross_backend_synthesis_complete",
        "nh_r4_complete",
    ]
    for key in expected_false:
        if completed[key] is not False:
            raise RuntimeError("pending work incorrectly marked complete: " + key)

    forbidden = c["forbidden_before_verified_bundle_and_new_host_e2"]
    if not forbidden or not all(value is True for value in forbidden.values()):
        raise RuntimeError("pre-bundle forbidden boundary weakened")

    b = c["blocked_bundle"]["artifacts"]
    if b["AdventureWorksDW2022.bak"]["sha256"] != "ac4a39502645c31f114331be28ce671ac5f70b0645f2aa59d8dccfbaae081c05":
        raise RuntimeError("seed hash changed")
    if b["exact_runtime_images.tar"]["sha256"] != "22eba9990c871c0fb719757d0310d2e1609f4d9bddcb0b0665f35c1f8f02a7fd":
        raise RuntimeError("runtime image tar hash changed")

    emo = c["pinned_emondrian_authority"]
    if emo["war_sha256"] != "100895f17acd4e4d3e3af58c2fbd442d95ca71fb969169d4c1a66acb974c52db":
        raise RuntimeError("eMondrian WAR pin changed")
    if emo["tomcat_linux_amd64_digest"] != "sha256:81be7f8d435228148a6419d5e967e6c31f094ec3a492055b42c66d2bb775627c":
        raise RuntimeError("Tomcat digest changed")
    if emo["historical_exact_runtime_reconstruction_claim_authorized"] is not False:
        raise RuntimeError("historical exact-runtime claim unexpectedly authorized")

    if s["e7_new_head"] != PARENT or s["e7_remote_publication_pass"] is not True:
        raise RuntimeError("E7 publication snapshot changed")
    for key in [
        "scientific_rerun_required",
        "runtime_materialization_authorized",
        "measurement_authorized",
        "real_effect_analysis_authorized",
        "historical_q1_q6_rerun_authorized",
        "sql_direct_rerun_authorized",
        "d4_recomputation_authorized",
    ]:
        if s[key] is not False:
            raise RuntimeError("E8 snapshot boundary changed: " + key)


def main() -> None:
    verify_lineage()
    verify_e7()
    verify_contract()

    print("e7_parent_and_static_lineage=PASS")
    print("published_e7_authority_blobs=PASS")
    print("e7_synthetic_verifier_replay=PASS")
    print("bundle_independent_r3e_static_work_complete=true")
    print("runtime_materialization_complete=false")
    print("xmla_measured_execution_complete=false")
    print("xmla_real_inference_complete=false")
    print("scientific_rerun_required=false")
    print("bundle_recovery_required=true")
    print("new_host_e2_read_only_revalidation_required=true")
    print("materialization_authorized=false")
    print("measurement_authorized=false")
    print("real_effect_analysis_authorized=false")
    print("historical_q1_q6_rerun_authorized=false")
    print("sql_direct_rerun_authorized=false")
    print("d4_recomputation_authorized=false")
    print("manuscript_bundle_independent_work_authorized=true")
    print("R3_E8_PRE_BUNDLE_STATIC_COMPLETION_VERIFY=PASS")


if __name__ == "__main__":
    main()
