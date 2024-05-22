import pandas as pd
from sklearn.metrics import classification_report, accuracy_score, f1_score, precision_score, recall_score
import xgboost as xgb
import numpy as np
import cupy as cp
from tqdm import tqdm
from sys import argv

emb_dataset_path = argv[1]
orig_dataset_path = argv[2]

df_orig = pd.read_csv(orig_dataset_path)
df_emb = pd.read_json(emb_dataset_path)

df_emb.rename(columns={'input':'reaction'}, inplace=True)
df = pd.merge(df_orig, df_emb, on='reaction')

df['classes'] = df['high_yielding']

X_train = df[df.split=='train'].embedding.tolist()
X_val = df[df.split=='val'].embedding.tolist()
X_test = df[df.split=='test'].embedding.tolist()
y_train = df[df.split=='train'].classes.tolist()
y_val = df[df.split=='val'].classes.tolist()
y_test = df[df.split=='test'].classes.tolist()

X_train = cp.array(X_train)
X_val = cp.array(X_val)
X_test = cp.array(X_test)
y_train = cp.array(y_train)
y_val = cp.array(y_val)
y_test = cp.array(y_test)

# Grid-search
result = pd.DataFrame()
accuracy_s = []
accuracy_train_s = []
parameters_s = []

for max_depth in tqdm([2, 4, 6, 8, 10]):
    for learning_rate in [0.01, 0.05, 0.1]:
        for n_estimators in [100, 200, 300, 400, 500]:
            for gamma in [0.1, 0.5, 1, 1.5]:
                for colsample_bytree in [0.5, 0.7, 0.9]:
                    parameters = {
                        'max_depth': max_depth,
                        'learning_rate': learning_rate,
                        'n_estimators': n_estimators,
                        'gamma': gamma,
                        'colsample_bytree': colsample_bytree
                    }
                    model = xgb.XGBClassifier(**parameters, random_state=42, tree_method='hist', device='cuda')
                    model.fit(X_train, y_train)
                    
                    preds_val = model.predict(X_val)
                    accuracy = accuracy_score(y_val.get(), preds_val)
                    
                    preds_train = model.predict(X_train)
                    accuracy_train = accuracy_score(y_train.get(), preds_train)
                    
                    parameters_s.append(parameters)
                    accuracy_s.append(accuracy)
                    accuracy_train_s.append(accuracy_train)
                    
result['parameters'] = parameters_s
result['test_accuracy'] = accuracy_s
result['train_accuracy'] = accuracy_train_s
result.to_csv('grid_search_results.csv', index=False)

result = result[result.train_accuracy <= 0.95]
best_score = result.test_accuracy.max()
best_params = result[result.test_accuracy==best_score].parameters.tolist()[0]
print(f'Best params: {best_params}\nBest score: {best_score}')

# Statistical evaluation of the best hyperparameters
acc = []
acc_t = []
f1 = []
for seed in [36, 42, 84, 200, 12345]:
  model = xgb.XGBClassifier(**best_params, random_state=seed, tree_method='hist', device='cuda')
  model.fit(X_train, y_train)
  
  preds_test = model.predict(X_test)
  acc_test = accuracy_score(y_test.get(), preds_test)
  f1_test = f1_score(y_test.get(), preds_test)
  
  preds_train = model.predict(X_train)
  acc_train = accuracy_score(y_train.get(), preds_train)
  
  acc.append(acc_test)
  acc_t.append(acc_train)
  f1.append(f1_test)

print(f'Accuracy: {np.round(np.mean(acc), 2)}+-{np.round(np.std(acc), 2)}')
print(f'F1-score: {np.round(np.mean(f1), 2)}+-{np.round(np.std(f1), 2)}')
print(f'Train accuracy: {np.round(np.mean(acc_t), 2)}+-{np.round(np.std(acc_t), 2)}')