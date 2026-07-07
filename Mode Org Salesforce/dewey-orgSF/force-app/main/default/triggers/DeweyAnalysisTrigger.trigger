trigger DeweyAnalysisTrigger on DeweyAnalysis__c (before delete) {
    if (Trigger.isBefore && Trigger.isDelete) {
        DeweyAnalysisTriggerHandler.onBeforeDelete(Trigger.old);
    }
}
