"""Tests de la detection d'auto-recursion Apex (APEX-REL-002)."""
from __future__ import annotations

from src.analyzer.apex_analyzer_helpers import (
    _detect_self_recursive_methods,
    _detect_trigger_after_save_recursion,
)


class TestSelfRecursionDetection:
    def test_true_recursion_is_reported(self) -> None:
        body = """
        public class TreeWalker {
            private Integer depthOf(Node node) {
                if (node.parent == null) { return 0; }
                return 1 + depthOf(node.parent);
            }
        }
        """
        assert _detect_self_recursive_methods(body) == ["depthOf(Node)"]

    def test_this_qualified_recursion_is_reported(self) -> None:
        body = """
        public class TreeWalker {
            private Integer depthOf(Node node) {
                return 1 + this.depthOf(node.parent);
            }
        }
        """
        assert _detect_self_recursive_methods(body) == ["depthOf(Node)"]

    def test_class_qualified_recursion_is_reported(self) -> None:
        body = """
        public class TreeWalker {
            private Integer depthOf(Node node) {
                return 1 + TreeWalker.depthOf(node.parent);
            }
        }
        """
        assert _detect_self_recursive_methods(body) == ["depthOf(Node)"]

    def test_homonym_on_another_class_is_not_recursion(self) -> None:
        body = """
        public class AccountIntegrationCallable implements Callable {
            private Map<String, Object> completeSirenisation(Map<String, Object> args) {
                Map<String, Object> output = new Map<String, Object>();
                new AccountService().completeSirenisation(entrepriseId, etablissementId, siren, siret);
                output.put('success', true);
                return output;
            }
        }
        """
        assert _detect_self_recursive_methods(body) == []

    def test_homonym_on_an_instance_variable_is_not_recursion(self) -> None:
        body = """
        public class AccountIntegrationCallable {
            private AccountService service;
            private void completeSirenisation(Id entrepriseId) {
                service.completeSirenisation(entrepriseId);
            }
        }
        """
        assert _detect_self_recursive_methods(body) == []

    def test_unrelated_static_member_does_not_suppress_the_finding(self) -> None:
        """Avant, le simple mot `static` desactivait la regle sur toute la classe."""
        body = """
        public class TreeWalker {
            public static final Integer MAX_DEPTH = 10;
            public static Integer depthOf(Node node) {
                return 1 + depthOf(node.parent);
            }
        }
        """
        assert _detect_self_recursive_methods(body) == ["depthOf(Node)"]

    def test_declared_but_never_read_guard_does_not_suppress_the_finding(self) -> None:
        body = """
        public class TreeWalker {
            private static Boolean isRunning = false;
            private Integer depthOf(Node node) {
                isRunning = true;
                return 1 + depthOf(node.parent);
            }
        }
        """
        assert _detect_self_recursive_methods(body) == ["depthOf(Node)"]

    def test_boolean_flag_guard_suppresses_the_finding(self) -> None:
        body = """
        public class TreeWalker {
            private static Boolean isRunning = false;
            private void walk(Node node) {
                if (isRunning) { return; }
                isRunning = true;
                walk(node.parent);
            }
        }
        """
        assert _detect_self_recursive_methods(body) == []

    def test_processed_id_set_guard_suppresses_the_finding(self) -> None:
        body = """
        public class AccountSync {
            private static Set<Id> processedIds = new Set<Id>();
            private void sync(Id accountId) {
                if (processedIds.contains(accountId)) { return; }
                processedIds.add(accountId);
                sync(parentOf(accountId));
            }
        }
        """
        assert _detect_self_recursive_methods(body) == []

    def test_guard_held_by_another_class_suppresses_the_finding(self) -> None:
        body = """
        public class AccountSync {
            private void sync(Id accountId) {
                if (TriggerBypass.skipAll) { return; }
                sync(parentOf(accountId));
            }
        }
        """
        assert _detect_self_recursive_methods(body) == []

    def test_guard_on_another_method_does_not_suppress_the_finding(self) -> None:
        body = """
        public class AccountSync {
            private static Boolean isRunning = false;
            public void run(Id accountId) {
                if (isRunning) { return; }
                isRunning = true;
                walk(accountId);
            }
            private void walk(Id accountId) {
                walk(parentOf(accountId));
            }
        }
        """
        assert _detect_self_recursive_methods(body) == ["walk(Id)"]

    def test_constructor_call_of_a_homonym_inner_class_is_not_recursion(self) -> None:
        body = """
        public class ResultBuilder {
            private Object buildPayload(Map<String, Object> args) {
                return new buildPayload(args);
            }
        }
        """
        assert _detect_self_recursive_methods(body) == []


class TestOverloadResolution:
    def test_delegation_to_an_overload_with_more_arguments_is_not_recursion(self) -> None:
        body = """
        public class AccountSync {
            public void sync(Id accountId) {
                sync(accountId, false);
            }
            public void sync(Id accountId, Boolean force) {
                doWork(accountId, force);
            }
        }
        """
        assert _detect_self_recursive_methods(body) == []

    def test_delegation_to_an_overload_with_fewer_arguments_is_not_recursion(self) -> None:
        body = """
        public class AccountSync {
            public void sync(Id accountId, Boolean force) {
                sync(accountId);
            }
            public void sync(Id accountId) {
                doWork(accountId);
            }
        }
        """
        assert _detect_self_recursive_methods(body) == []

    def test_same_arity_overload_with_different_types_is_not_recursion(self) -> None:
        body = """
        public class AccountSync {
            public void sync(Id accountId) {
                String externalKey = keyOf(accountId);
                sync(externalKey);
            }
            public void sync(String externalKey) {
                doWork(externalKey);
            }
        }
        """
        assert _detect_self_recursive_methods(body) == []

    def test_recursion_on_the_matching_overload_is_reported(self) -> None:
        body = """
        public class AccountSync {
            public void sync(Id accountId) {
                doWork(accountId);
            }
            public void sync(Id accountId, Boolean force) {
                sync(accountId, force);
            }
        }
        """
        assert _detect_self_recursive_methods(body) == ["sync(Id, Boolean)"]

    def test_string_literal_argument_is_counted(self) -> None:
        """Les litteraux sont blanchis : sans marqueurs, `f('a')` passerait pour `f()`."""
        body = """
        public class AccountSync {
            public void sync(String externalKey) {
                sync('ACME-001');
            }
            public void sync() {
                doWork();
            }
        }
        """
        assert _detect_self_recursive_methods(body) == ["sync(String)"]

    def test_ambiguous_argument_type_is_not_reported(self) -> None:
        """Deux surcharges de meme arite et un type indecidable : on s'abstient."""
        body = """
        public class AccountSync {
            public void sync(Id accountId) {
                sync(resolveTarget());
            }
            public void sync(String externalKey) {
                doWork(externalKey);
            }
        }
        """
        assert _detect_self_recursive_methods(body) == []

    def test_generic_parameter_signature_is_matched(self) -> None:
        body = """
        public class AccountIntegrationCallable {
            private Map<String, Object> completeSirenisation(Map<String, Object> args) {
                return completeSirenisation(args);
            }
        }
        """
        assert _detect_self_recursive_methods(body) == [
            "completeSirenisation(Map<String,Object>)"
        ]

    def test_homonym_overload_on_another_class_is_still_ignored(self) -> None:
        body = """
        public class AccountIntegrationCallable implements Callable {
            private Map<String, Object> completeSirenisation(Map<String, Object> args) {
                Map<String, Object> output = new Map<String, Object>();
                new AccountService().completeSirenisation(entrepriseId, etablissementId, siren, siret);
                output.put('success', true);
                return output;
            }
        }
        """
        assert _detect_self_recursive_methods(body) == []


class TestTriggerAfterSaveRecursion:
    def test_after_update_dml_on_trigger_new_is_reported(self) -> None:
        body = """
        trigger AccountTrigger on Account (after insert, after update) {
            update Trigger.new;
        }
        """
        result = _detect_trigger_after_save_recursion(body)
        assert result is not None
        events, sample = result
        assert events == {"after insert", "after update"}
        assert "Trigger.new" in sample

    def test_static_flag_guard_suppresses_the_finding(self) -> None:
        body = """
        trigger AccountTrigger on Account (after update) {
            if (AccountTriggerHandler.isRunning) { return; }
            AccountTriggerHandler.isRunning = true;
            update Trigger.new;
        }
        """
        assert _detect_trigger_after_save_recursion(body) is None

    def test_unrelated_static_reference_does_not_suppress_the_finding(self) -> None:
        """Avant, une simple mention de `static` desactivait la regle."""
        body = """
        trigger AccountTrigger on Account (after update) {
            System.debug(AccountConstants.STATIC_LABEL);
            update Trigger.new;
        }
        """
        assert _detect_trigger_after_save_recursion(body) is not None
