import re #this package is useful for finding patters. It is called regular expression package
import pandas as pd # This package is useful for exploring and cleaning data
from collections import Counter #useful for python object
df = pd.read_csv("JCM_mediumID_mediumName (1).csv") #this code enable the python to read the file
print(df)
#create an empty counter
unit_counter = Counter() #this line of code creates an empty dictionary
# Creation of regular expression patterns
pattern = r'\\mono\{[^}]+\}\s*\{[^}]+\}\s*\{([^}]*)\}' #since the data pattern has ingredient, amount and data this patters tries to capture only the last part which is the units
#read every medium
for text in df["tex_text"].fillna(""):
  units = re.findall(pattern,text) #this line of code means to find every unit
#count everything
  for unit in units:
      unit_counter[unit]+= 1
#conver to dataframe
unit_df = pd.DataFrame(
    unit_counter.items(),
    columns=["Unit","Count"]

)
#sort the data
unit_df = unit_df.sort_values(
    by="Count",
    ascending=False
)
#save in a csv file
unit_df.to_csv(
    "unit_statistic.csv",
    index=False
)
print(unit_df)
import pandas as pd
import re
from collections import Counter

ingredient_counter = Counter()

pattern = r'\\mono\{([^{}]+)\}'

for text in df["tex_text"].fillna(""):
    ingredients = re.findall(pattern, text) #find every ingredient
    for ingredient in ingredients:
        ingredient = ingredient.strip()
        ingredient_counter[ingredient] += 1
#convert to dataframe
ingredient_df = pd.DataFrame(
    ingredient_counter.items(),
    columns=["Ingredient", "Frequency"]
)

ingredient_df = ingredient_df.sort_values(
    by="Frequency",
    ascending=False
)

ingredient_df.to_csv("ingredient_frequency.csv", index=False)

print(ingredient_df)




















