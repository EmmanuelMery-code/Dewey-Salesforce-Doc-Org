/**
 * DeweyAnalysisTriggerHandler
 *
 * Handles cascade deletion of DeweyFinding__c records when a DeweyAnalysis__c
 * is deleted. DeweyAnalysisFinding__c junction records are automatically
 * cascade-deleted by Salesforce (MasterDetail). This handler handles findings:
 * only findings with no remaining junction records are deleted.
 */
public with sharing class DeweyAnalysisTriggerHandler {

    /**
     * Called from trigger before delete context.
     * Deletes DeweyFinding__c records that are exclusively linked
     * to the analyses being deleted (no other analysis junctions).
     */
    public static void onBeforeDelete(List<DeweyAnalysis__c> analyses) {
        Set<Id> analysisIds = new Map<Id, DeweyAnalysis__c>(analyses).keySet();

        // Step 1 — find all findings linked to the analyses being deleted
        List<DeweyAnalysisFinding__c> junctions = [
            SELECT DeweyFinding__c
            FROM DeweyAnalysisFinding__c
            WHERE DeweyAnalysis__c IN :analysisIds
            AND DeweyFinding__c != null
        ];

        if (junctions.isEmpty()) {
            return;
        }

        Set<Id> findingIds = new Set<Id>();
        for (DeweyAnalysisFinding__c j : junctions) {
            findingIds.add(j.DeweyFinding__c);
        }

        // Step 2 — among those findings, identify which ones have junction
        // records pointing to OTHER analyses (not being deleted)
        List<DeweyAnalysisFinding__c> otherJunctions = [
            SELECT DeweyFinding__c
            FROM DeweyAnalysisFinding__c
            WHERE DeweyFinding__c IN :findingIds
            AND DeweyAnalysis__c NOT IN :analysisIds
        ];

        Set<Id> findingsLinkedElsewhere = new Set<Id>();
        for (DeweyAnalysisFinding__c j : otherJunctions) {
            findingsLinkedElsewhere.add(j.DeweyFinding__c);
        }

        // Step 3 — delete only findings that are exclusively in the deleted analyses
        List<DeweyFinding__c> toDelete = new List<DeweyFinding__c>();
        for (Id fId : findingIds) {
            if (!findingsLinkedElsewhere.contains(fId)) {
                toDelete.add(new DeweyFinding__c(Id = fId));
            }
        }

        if (!toDelete.isEmpty()) {
            delete toDelete;
        }
    }
}
