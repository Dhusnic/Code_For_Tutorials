import pandas as pd

from sklearn.neighbors import KNeighborsClassifier
df=pd.read_csv(r"D:\Code for tutorials\Machine Learning\datasets\supervised Learnings\classification\KNN\IRIS.csv")

model=KNeighborsClassifier()
model.fit(df[['sepal_length','sepal_width','petal_length','petal_width']],df['species'])
input_data=[5.1,3.5,1.4,0.2]
result=model.predict([input_data]) #This will give you the predicted species for the input data
print (df.head())
print(result)

#visualization
import matplotlib.pyplot as plt
plt.scatter(df['sepal_length'],df['sepal_width'],c=df['species'])