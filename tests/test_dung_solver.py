"""Unit tests for dung_solver.py — pure computation, no mocking needed."""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dung_solver import ArgumentationFramework, build_framework


# ── Construction ─────────────────────────────────────────────────────────

class TestConstruction:
    def test_add_argument(self):
        af = ArgumentationFramework()
        af.add_argument("a")
        assert "a" in af.arguments

    def test_add_attack(self):
        af = ArgumentationFramework()
        af.add_attack("a", "b")
        assert ("a", "b") in af.attacks

    def test_add_attack_auto_adds_arguments(self):
        af = ArgumentationFramework()
        af.add_attack("x", "y")
        assert "x" in af.arguments
        assert "y" in af.arguments


# ── Queries ──────────────────────────────────────────────────────────────

class TestQueries:
    def test_attackers_of(self, sample_framework):
        assert sample_framework.attackers_of("B") == {"A"}
        assert sample_framework.attackers_of("A") == set()

    def test_attacked_by(self, sample_framework):
        assert sample_framework.attacked_by("A") == {"B"}
        assert sample_framework.attacked_by("C") == set()

    def test_is_conflict_free_true(self, sample_framework):
        assert sample_framework.is_conflict_free({"A", "C"})

    def test_is_conflict_free_false(self, sample_framework):
        assert not sample_framework.is_conflict_free({"A", "B"})

    def test_defends(self, sample_framework):
        # A defends C because A attacks B (the only attacker of C)
        assert sample_framework.defends({"A"}, "C")

    def test_does_not_defend(self, sample_framework):
        # Empty set does not defend C (B attacks C, nobody counter-attacks B)
        assert not sample_framework.defends(set(), "C")

    def test_is_admissible(self, sample_framework):
        assert sample_framework.is_admissible({"A", "C"})

    def test_is_not_admissible(self, sample_framework):
        # {B} is not admissible — B is attacked by A and B doesn't attack A
        assert not sample_framework.is_admissible({"B"})


# ── Grounded Extension ──────────────────────────────────────────────────

class TestGrounded:
    def test_linear_chain(self, sample_framework):
        # A→B→C: grounded = {A, C}
        assert sample_framework.grounded_extension() == {"A", "C"}

    def test_empty_framework(self):
        af = ArgumentationFramework()
        assert af.grounded_extension() == set()

    def test_no_attacks(self):
        af = ArgumentationFramework()
        af.add_argument("a")
        af.add_argument("b")
        assert af.grounded_extension() == {"a", "b"}

    def test_self_attack(self):
        af = ArgumentationFramework()
        af.add_attack("a", "a")
        assert af.grounded_extension() == set()

    def test_even_cycle(self):
        # a↔b: grounded = {} (neither can be accepted)
        af = ArgumentationFramework()
        af.add_attack("a", "b")
        af.add_attack("b", "a")
        assert af.grounded_extension() == set()

    def test_odd_cycle(self):
        # a→b→c→a: grounded = {}
        af = ArgumentationFramework()
        af.add_attack("a", "b")
        af.add_attack("b", "c")
        af.add_attack("c", "a")
        assert af.grounded_extension() == set()


# ── Preferred Extensions ─────────────────────────────────────────────────

class TestPreferred:
    def test_linear_chain(self, sample_framework):
        pref = sample_framework.preferred_extensions()
        assert len(pref) == 1
        assert pref[0] == {"A", "C"}

    def test_even_cycle_two_extensions(self):
        af = ArgumentationFramework()
        af.add_attack("a", "b")
        af.add_attack("b", "a")
        pref = af.preferred_extensions()
        pref_sorted = sorted([frozenset(s) for s in pref])
        assert frozenset({"a"}) in pref_sorted
        assert frozenset({"b"}) in pref_sorted


# ── Stable Extensions ───────────────────────────────────────────────────

class TestStable:
    def test_linear_chain(self, sample_framework):
        stable = sample_framework.stable_extensions()
        assert len(stable) == 1
        assert stable[0] == {"A", "C"}

    def test_even_cycle(self):
        af = ArgumentationFramework()
        af.add_attack("a", "b")
        af.add_attack("b", "a")
        stable = af.stable_extensions()
        stable_sorted = sorted([frozenset(s) for s in stable])
        assert frozenset({"a"}) in stable_sorted
        assert frozenset({"b"}) in stable_sorted

    def test_odd_cycle_no_stable(self):
        af = ArgumentationFramework()
        af.add_attack("a", "b")
        af.add_attack("b", "c")
        af.add_attack("c", "a")
        assert af.stable_extensions() == []


# ── Argument Status ──────────────────────────────────────────────────────

class TestArgumentStatus:
    def test_linear_chain(self, sample_framework):
        status = sample_framework.argument_status()
        assert status["A"] == "accepted"
        assert status["B"] == "rejected"
        assert status["C"] == "accepted"

    def test_cycle_all_undecided(self):
        af = ArgumentationFramework()
        af.add_attack("a", "b")
        af.add_attack("b", "a")
        status = af.argument_status()
        assert status["a"] == "undecided"
        assert status["b"] == "undecided"

    def test_self_attack_and_unattacked(self):
        af = ArgumentationFramework()
        af.add_attack("a", "a")
        af.add_argument("b")
        status = af.argument_status()
        assert status["a"] == "undecided"
        assert status["b"] == "accepted"


# ── Full Analysis ────────────────────────────────────────────────────────

class TestFullAnalysis:
    def test_structure(self, sample_framework):
        result = sample_framework.full_analysis()
        assert "arguments" in result
        assert "attacks" in result
        assert "grounded_extension" in result
        assert "preferred_extensions" in result
        assert "stable_extensions" in result
        assert "argument_status" in result
        assert "summary" in result

    def test_summary_counts(self, sample_framework):
        summary = sample_framework.full_analysis()["summary"]
        assert summary["total_arguments"] == 3
        assert summary["accepted"] == 2
        assert summary["rejected"] == 1
        assert summary["undecided"] == 0


# ── build_framework ──────────────────────────────────────────────────────

class TestBuildFramework:
    def test_from_dict(self):
        claims = [{"id": "c1", "text": "X"}, {"id": "c2", "text": "Y"}]
        attacks = [{"from": "c1", "to": "c2", "reason": "contradiction"}]
        af = build_framework(claims, attacks)
        assert "c1" in af.arguments
        assert "c2" in af.arguments
        assert ("c1", "c2") in af.attacks

    def test_no_attacks(self):
        claims = [{"id": "c1", "text": "X"}, {"id": "c2", "text": "Y"}]
        af = build_framework(claims, [])
        assert af.grounded_extension() == {"c1", "c2"}
