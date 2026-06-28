import pandas as pd
import re


df = pd.read_csv("JCM_mediumID_mediumName.csv")

#column name of the file i want to anylyze
column_name = "tex_text"


# REGEX PATTERNS


mono_pattern = r'\\\\?mono\{'
chu_pattern = r'\\\\?chu\{'

# STORAGE


results = []

composition_count = 0
preparation_count = 0
unknown_count = 0


# PROCESS EACH ROW


for idx, text in enumerate(df["tex_text"].fillna("")):

    text = str(text)

    # Split whenever a new command starts
    pieces = re.split(r'(?=\\\\?mono\{)|(?=\\\\?chu\{)', text)

    for piece in pieces:

        piece = piece.strip()

        if not piece:
            continue

        if re.match(mono_pattern, piece):

            category = "Concentration Composition"
            composition_count += 1

        elif re.match(chu_pattern, piece):

            category = "Preparation Method"
            preparation_count += 1

        else:

            category = "Unknown"
            unknown_count += 1

        results.append({
            "row_number": idx,
            "content": piece,
            "category": category
        })



results_df = pd.DataFrame(results)

results_df.to_csv(
    "medium_classification_result.csv",
    index=False
)



print("\nClassification Summary")
print("-" * 40)

print(f"Concentration Composition : {composition_count}")
print(f"Preparation Method       : {preparation_count}")
print(f"Unknown                  : {unknown_count}")

print(f"\nTotal Classified Lines   : {len(results_df)}")