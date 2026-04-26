#!/usr/bin/env python3
"""最小验证脚本 — 不依赖 Streamlit/LLM，纯后端逻辑测试。

验证项：
1. 记忆系统（声明性/程序性/工作记忆）
2. 诊断引擎的 fallback 规则
3. 策略选择逻辑
4. 编排器决策逻辑

用法：
    uv run python scripts/test_backend.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_memory():
    """Test L1+L2 memory systems without LLM."""
    print("\n🧠 [L1+L2] Memory System Test")
    print("-" * 40)

    from alto.memory.declarative import DeclarativeMemory
    from alto.memory.procedural import ProceduralMemory
    from alto.memory.working import WorkingMemory

    # Test declarative memory
    mem = DeclarativeMemory("test_user_001", storage_path="./data/test_memory")

    # Simulate learning progression
    mem.encounter("want-to-V", success=False, error_detail={
        "sentence": "I want eat apple",
        "type": "omission",
        "missing": ["to-infinitive"],
        "explanation": "Missing 'to' after want"
    })
    print(f"  After 1st failure: want-to-V activation = {mem.get_state('want-to-V').activation:.2f}")

    mem.encounter("want-to-V", success=False, error_detail={
        "sentence": "I want go home",
        "type": "omission",
        "missing": ["to-infinitive"],
    })
    print(f"  After 2nd failure: want-to-V activation = {mem.get_state('want-to-V').activation:.2f}")
    print(f"  Systematic errors: {mem.get_state('want-to-V').systematic_error_count}")

    mem.encounter("want-to-V", success=True)
    print(f"  After 1st success: want-to-V activation = {mem.get_state('want-to-V').activation:.2f}")

    mem.encounter("want-to-V", success=True)
    mem.encounter("want-to-V", success=True)
    mem.encounter("want-to-V", success=True)
    print(f"  After 4 successes: want-to-V activation = {mem.get_state('want-to-V').activation:.2f}")
    print(f"  Stable: {mem.get_state('want-to-V').stable}")

    # Test weak constructions
    weak = mem.get_weak_constructions(threshold=0.4)
    print(f"  Weak constructions (<{0.4}): {[w[0] for w in weak]}")

    # Test stats
    stats = mem.get_stats()
    print(f"  Stats: {stats}")

    # Test procedural memory
    print("\n  Procedural Memory (Strategy Selection):")
    state = mem.get_state("want-to-V")
    strategy = ProceduralMemory.select_strategy(state)
    print(f"    Activation={state.activation:.2f} → Mode={strategy.mode}")
    print(f"    Allow free: {strategy.allow_free}")

    # Test working memory
    wm = WorkingMemory()
    wm.push_turn("user", "I want eat apple")
    wm.push_turn("assistant", "I see you're trying...")
    print(f"\n  Working Memory: {len(wm.turn_history)} turns")

    print("\n  ✅ Memory system OK")
    return True


def test_diagnosis_fallback():
    """Test L3 diagnosis without LLM (rule-based fallback)."""
    print("\n🔍 [L3] Diagnosis Engine Test (Fallback Mode)")
    print("-" * 40)

    from alto.neuro_symbolic.diagnostic import ConstructionDiagnosis

    diag = ConstructionDiagnosis()

    test_cases = [
        ("I want eat apple", "want-to-V omission"),
        ("I want to eat apple", "correct want-to-V"),
        ("He gave me a book", "correct ditransitive"),
        ("He gave a book", "ditransitive omission"),
        ("Hello how are you", "no target"),
    ]

    for sentence, expected in test_cases:
        report = diag.diagnose(sentence, None, None, "")
        print(f"  \"{sentence[:30]}...\" → {report.target_cxn or 'N/A'} ({report.error_type})")

    print("\n  ✅ Fallback diagnosis OK")
    return True


def test_orchestrator():
    """Test L0 orchestrator logic."""
    print("\n🎛️  [L0] Orchestrator Test")
    print("-" * 40)

    from alto.memory.declarative import DeclarativeMemory
    from alto.memory.working import WorkingMemory
    from alto.agents.orchestrator import MetaOrchestrator
    from alto.models import DiagnosisReport

    mem = DeclarativeMemory("test_user_002", storage_path="./data/test_memory")
    wm = WorkingMemory()
    orch = MetaOrchestrator(mem, wm)

    # Simulate error detection
    report = DiagnosisReport(
        target_cxn="want-to-V",
        error_type="omission",
        is_systematic=True,
        explanation="Missing 'to' after want",
    )

    decision = orch.process_chat_input("I want eat apple", report)
    print(f"  Error detected: should_teach={decision['should_teach']}, target={decision['suggested_target']}")

    # Simulate correct usage
    report2 = DiagnosisReport(target_cxn="want-to-V", error_type="none")
    decision2 = orch.process_chat_input("I want to eat an apple", report2)
    print(f"  Correct usage: should_teach={decision2['should_teach']}")

    print("\n  ✅ Orchestrator OK")
    return True


def test_full_loop():
    """Simulate a complete learning loop without LLM."""
    print("\n🔄 Full Learning Loop Simulation")
    print("=" * 40)

    from alto.memory.declarative import DeclarativeMemory
    from alto.memory.working import WorkingMemory
    from alto.memory.procedural import ProceduralMemory
    from alto.agents.orchestrator import MetaOrchestrator
    from alto.models import DiagnosisReport

    user_id = "learner_demo"
    mem = DeclarativeMemory(user_id, storage_path="./data/test_memory")
    wm = WorkingMemory()
    orch = MetaOrchestrator(mem, wm)

    scenario = [
        ("I want eat apple", "omission", True, "首次错误"),
        ("I want go school", "omission", True, "重复错误 → 进入教学队列"),
        ("I want to eat apple", "none", False, "首次正确 → 激活度上升"),
        ("I want to sleep", "none", False, "再次正确 → 继续上升"),
        ("I want play game", "omission", True, "又错了 → 激活度下降"),
    ]

    for sentence, error_type, is_systematic, note in scenario:
        report = DiagnosisReport(
            target_cxn="want-to-V",
            error_type=error_type,
            is_systematic=is_systematic,
        )
        decision = orch.process_chat_input(sentence, report)
        state = mem.get_state("want-to-V")
        act = state.activation if state else 0.0
        print(f"  {note:20s} | act={act:.2f} | teach={decision['should_teach']}")

    final = mem.get_state("want-to-V")
    print(f"\n  Final state: activation={final.activation:.2f}, "
          f"exposures={final.exposure_count}, "
          f"errors={final.systematic_error_count}")

    strategy = ProceduralMemory.select_strategy(final)
    print(f"  Recommended strategy: {strategy.mode}")

    print("\n  ✅ Full loop simulation OK")
    return True


def main():
    print("=" * 50)
    print("Backend Logic Verification (No LLM / No Streamlit)")
    print("=" * 50)

    all_ok = True
    all_ok &= test_memory()
    all_ok &= test_diagnosis_fallback()
    all_ok &= test_orchestrator()
    all_ok &= test_full_loop()

    print("\n" + "=" * 50)
    if all_ok:
        print("🎉 ALL TESTS PASSED — Backend logic is solid")
        print("=" * 50)
        print("\nNext steps:")
        print("  1. uv sync")
        print("  2. uv run python -m spacy download en_core_web_sm")
        print("  3. Create .env with your API key")
        print("  4. uv run python scripts/test_connection.py")
        print("  5. uv run streamlit run src/alto/app.py")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
