import asyncio
import os
import sys

# Add src to python path so imports work
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from src.services.llm import analyze_content

def main():
    if not os.getenv("GITHUB_ACCESS_TOKEN"):
        print("Error: GITHUB_ACCESS_TOKEN not set!")
        return

    test_content = """
    A major political event happened in Johannesburg today. The ruling party announced a new policy regarding the energy sector.
    """
    
    print("Testing LLM analysis with GitHub Models...")
    try:
        result = analyze_content(test_content, niche="politics")
        print("\n--- Result ---")
        print(f"Sentiment: {result.sentiment}")
        print(f"Category: {result.category}")
        print(f"Entities: {result.key_entities}")
        print(f"Summary: {result.summary}")
        print(f"Location: {result.location}, {result.city}, {result.country}")
        print(f"Is SA: {result.is_south_africa}")
    except Exception as e:
        print(f"Analysis failed: {e}")

if __name__ == "__main__":
    main()
