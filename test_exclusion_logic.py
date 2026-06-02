from pathlib import Path
from src.parsers.salesforce_parser import SalesforceMetadataParser

# Mock log callback
def log(msg):
    print(f"LOG: {msg}")

# Initialize parser with the exclusion file
parser = SalesforceMetadataParser(
    source_dir=".",
    exclusion_config_path=r"C:\Users\emery\Desktop\Dewey\org\sandbox int\exclusion.json",
    log_callback=log
)

print("\nExclusion Rules loaded:")
for cat, rules in parser.exclusion_rules.items():
    if rules:
        print(f"  {cat}: {rules}")

    # Test exclusion for the specific flow
    flow_name = "sfpegMassActionTest"
    is_ex = parser._is_excluded("permission_set", flow_name)
    print(f"\nIs '{flow_name}' excluded for category 'permission_set'? {is_ex}")

# Test with different casing or spaces
print(f"Is 'demo_creation_decouverte' excluded? {parser._is_excluded('flow', 'demo_creation_decouverte')}")
print(f"Is 'DEMO CREATION DECOUVERTE' excluded? {parser._is_excluded('flow', 'DEMO CREATION DECOUVERTE')}")
