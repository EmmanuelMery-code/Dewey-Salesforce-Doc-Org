from __future__ import annotations

SF_CLI_DOWNLOAD_URL = "https://developer.salesforce.com/tools/salesforcecli"
PMD_DOWNLOAD_URL = "https://pmd.github.io/latest/pmd_userdocs_installation.html"
ORG_CHECK_APP_URL = "https://appexchange.salesforce.com/appxListingDetail?listingId=a0N4V00000HA0X2UAL"
ORG_CHECK_GITHUB_URL = "https://github.com/SalesforceLabs/OrgCheck"

LOGIN_TARGETS = {
    "production": "https://login.salesforce.com",
    "sandbox": "https://test.salesforce.com",
    "custom": "",
}

LANGUAGES = {"fr": "Francais", "en": "English"}
ORG_CHECK_CHOICES = ["apex-classes", "global-view", "hardcoded-urls"]
AI_PROVIDERS = ["Gemini", "Claude", "Gateway"]

# Policies applied to the Source/Output folders right before an action
# (generate documentation, retrieve, ...) reads/writes them. See
# AppUiMixin._apply_source_dir_policy / _apply_output_dir_policy.
FOLDER_DIR_POLICIES = ("use_as_is", "empty_and_use", "dated_subfolder")
