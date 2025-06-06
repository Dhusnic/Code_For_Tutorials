import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import logging
import joblib
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score,accuracy_score,confusion_matrix,classification_report
from sklearn.preprocessing import StandardScaler,MinMaxScaler
# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class ML_Base_Controller:
    """
    A base class for performing basic feature correlation analysis
    and data visualization in machine learning workflows.
    """
    
    none_list = ["None", [], {}, [""], ""]

    def __init__(self):
        """
        Initialize the ML_Base_Controller and configure the logger.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("ML_Base_Controller initialized.")

    def feature_impact(self, data={}, label=""):
        """
        Visualize the correlation of each numeric feature with the specified label.

        Parameters:
        -----------
        data : pd.DataFrame
            The input dataset containing features and the target label.
        label : str
            The target column name to correlate with other numeric features.

        Returns:
        --------
        None. Displays a heatmap plot.

        Raises:
        -------
        TypeError : If 'data' is not a pandas DataFrame.
        ValueError : If 'label' is missing or not in the DataFrame.
        """
        try:
            if not isinstance(data, pd.DataFrame):
                raise TypeError("Input 'data' must be a pandas DataFrame.")

            if label in self.none_list or label not in data.columns:
                raise ValueError(f"Invalid or missing label column: {label}")

            self.logger.info(f"Generating correlation heatmap for label: {label}")

            corr = data.corr(numeric_only=True)

            if label not in corr.columns:
                raise ValueError(f"Label '{label}' not found in numeric correlation matrix.")

            plt.figure(figsize=(10, 6))
            sns.heatmap(
                corr[[label]].sort_values(by=label, ascending=False),
                annot=True,
                cmap="coolwarm",
            )
            plt.title(f"Feature Correlation with {label}")
            plt.tight_layout()
            plt.show()

        except Exception as e:
            self.logger.error(f"Error in feature_impact: {e}", exc_info=True)

    def feature_correlation(self, selected_features=[], data={}, label="", title=""):
        """
        Create a pair plot of selected features with respect to the label.

        Parameters:
        -----------
        selected_features : list
            A list of feature column names to include in the pair plot.
        data : pd.DataFrame
            The dataset containing the selected features and label.
        label : str
            The target variable name to be used for hue coloring.
        title : str
            Title of the plot (optional).

        Returns:
        --------
        None. Displays a seaborn pairplot.

        Raises:
        -------
        TypeError : If 'data' is not a pandas DataFrame.
        ValueError : If 'selected_features' or 'label' are invalid.
        """
        try:
            if not isinstance(data, pd.DataFrame):
                raise TypeError("Input 'data' must be a pandas DataFrame.")

            if not selected_features or not all(feature in data.columns for feature in selected_features):
                raise ValueError("Selected features must be a non-empty list of valid DataFrame columns.")

            if label in self.none_list or label not in data.columns:
                raise ValueError(f"Invalid or missing label column: {label}")

            self.logger.info(f"Generating pairplot for features: {selected_features} with label: {label}")

            sns.pairplot(
                data[selected_features + [label]],
                hue=label,
                palette="Set1",
                diag_kind="kde",
            )

            if title not in self.none_list:
                plt.suptitle(title, y=1.02)

            plt.figure(figsize=(10, 6))
            plt.tight_layout()
            plt.show()

        except Exception as e:
            self.logger.error(f"Error in feature_correlation: {e}", exc_info=True)

    def fill_missing_values(self, data={}, method="mean", columns=None):
        """
        Fill missing values in the dataset using the specified method.
        Parameters:
        -----------
        data : pd.DataFrame
            The input dataset with possible missing values.
        method : str
            The method to fill missing values ('mean', 'median', 'mode', or 'drop').
        columns : list or None, optional
            List of columns to apply the missing value strategy on.
            If None, applies to all columns.
        Returns:
        --------
        pd.DataFrame
            The dataset with missing values handled.
        Raises:
        -------
        TypeError
            If input data is not a pandas DataFrame.
        ValueError
            If method is not one of the supported options.
        """
        try:
            if not isinstance(data, pd.DataFrame):
                raise TypeError("Input 'data' must be a pandas DataFrame.")
            if method not in ["mean", "median", "mode", "drop"]:
                raise ValueError("Invalid method. Supported methods are 'mean', 'median', 'mode', or 'drop'.")
            if columns is not None:
                if not isinstance(columns, list) or not all(col in data.columns for col in columns):
                    raise ValueError("All specified columns must exist in the DataFrame.")
            target_cols = columns if columns else data.columns
            self.logger.info(f"Filling missing values in columns: {target_cols} using method: {method}")
            if method == "mean":
                for col in target_cols:
                    if pd.api.types.is_numeric_dtype(data[col]):
                        data[col] = data[col].fillna(data[col].mean())
            elif method == "median":
                for col in target_cols:
                    if pd.api.types.is_numeric_dtype(data[col]):
                        data[col] = data[col].fillna(data[col].median())
            elif method == "mode":
                for col in target_cols:
                    data[col] = data[col].fillna(data[col].mode().iloc[0])
            elif method == "drop":
                data = data.dropna(subset=target_cols)
            return data
        except Exception as e:
            self.logger.error(f"Error in fill_missing_values: {e}", exc_info=True)
            raise  # Good practice to re-raise after logging
    
    def fit_model(self, model, X_train, y_train, X_test, y_test,
                model_name="", save_model=False, model_path="", model_name_path=""):
        """
        Train a machine learning model, evaluate its accuracy, and optionally save it to disk.
        Parameters
        ----------
        model : object
            An initialized machine learning model object that implements `fit` and `predict`.
            
        X_train : pd.DataFrame
            Feature matrix for training.
            
        y_train : pd.Series or pd.DataFrame
            Target labels for training data.
            
        X_test : pd.DataFrame
            Feature matrix for testing.
            
        y_test : pd.Series or pd.DataFrame
            Target labels for testing data.
            
        model_name : str, optional
            A label for the model, used for logging and print statements. Default is "".
            
        save_model : bool, optional
            If True, saves the trained model using `joblib`. Default is False.
            
        model_path : str, optional
            The directory path to save the model (used only if `save_model` is True).
            
        model_name_path : str, optional
            The filename (with or without extension) used to save the model. Combined with `model_path`.
        Returns
        -------
        tuple
            Returns a tuple of (y_pred, trained_model, accuracy), where:
            - y_pred: array-like, the model's predictions on X_test
            - trained_model: the fitted model object
            - accuracy: float, accuracy score of the predictions compared to y_test
        Raises
        ------
        TypeError
            If `model_name`, `model_path`, or `model_name_path` is not a string, or if `save_model` is not a bool.
        Exception
            Any exception raised during model training, prediction, or saving is logged and re-raised.
        """
        try:
            if not isinstance(model_name, str):
                raise TypeError("model_name must be a string.")
            if not isinstance(save_model, bool):
                raise TypeError("save_model must be a boolean.")
            if not isinstance(model_path, str):
                raise TypeError("model_path must be a string.")
            if not isinstance(model_name_path, str):
                raise TypeError("model_name_path must be a string.")
            self.logger.info(f"Fitting model: {model_name}")
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)
            # Determine if it's a classifier or regressor
            if hasattr(model, "predict_proba") or hasattr(model, "classes_"):
                accuracy = accuracy_score(y_test, y_pred)
                self.logger.info(f"[Classification] Model: {model_name} - Accuracy: {accuracy*100:.4f}%")
            else:
                accuracy = r2_score(y_test, y_pred)
                mse = mean_squared_error(y_test, y_pred)
                self.logger.info(f"[Regression] Model: {model_name} - R2 Score: {accuracy*100:.4f}%, MSE: {mse:.4f}")
            print(f"Model: {model_name} - Score: {accuracy:.4f}")
            if save_model:
                model_full_path = model_path + model_name_path
                joblib.dump(model, model_full_path)
                self.logger.info(f"Model saved at: {model_full_path}")
            return y_pred, model, accuracy
        except Exception as e:
            self.logger.error(f"Error in fit_model: {e}", exc_info=True)
            raise
        
    def evaluate_model(self, y_test, y_pred,model,confusion_matrix_plot=False, model_name="", model_type="", save_results=False, results_path="", results_name=""):
        """
        Evaluate the performance of a trained model and optionally save the results.
        Parameters
        ----------
        y_test : array-like
            True labels for the test data.

        y_pred : array-like
            Predicted labels from the model.

        model : object
            An initialized machine learning model object that implements `predict`.
        
        model_name : str, optional
            A label for the model, used for logging and print statements. Default is "".

        model_type : str, optional
            A label for the model type, used for logging and print statements. Default is "".

        save_results : bool, optional
            If True, saves the evaluation results using `pandas`. Default is False.

        results_path : str, optional
            The directory path to save the results (used only if `save_results` is True).

        results_name : str, optional
            The filename (with or without extension) used to save the results. Combined with `results_ path`. 
            Raises
            ------
            TypeError
            If `model_name`, `model_type`, `results_path`, or `results_name` is not a string, or if `save_results` is not a bool.
        Exception
        Any exception raised during evaluation and saving is logged and re-raised.
        """
        try:
            if not isinstance(model_name, str):
                raise TypeError("model_ name must be a string.")
            if not isinstance(model_type, str):
                raise TypeError("model_type must be a string.")
            if not isinstance(save_results, bool):
                raise TypeError("save_results must be a boolean.")
            if not isinstance(results_path, str):
                raise TypeError("results_path must be a string.")
            if not isinstance(results_name, str):
                raise TypeError("results_name must be a string.")
            self.logger.info(f"Evaluating model: {model_name}")
            # Determine if it's a classifier or regressor
            if hasattr(model, "predict_proba") or hasattr(model, "classes_"):
                accuracy = accuracy_score(y_test, y_pred)
                mse=mean_squared_error(y_test, y_pred)
                classifi_report = classification_report(y_test, y_pred)
                self.logger.info(f"[Classification] Model: {model_name} - Accuracy: {accuracy*100:.4f}%")
                if confusion_matrix_plot:
                    sns.heatmap(confusion_matrix(y_test, y_pred), annot=True, fmt='d')
                    plt.show()
            else:
                accuracy = r2_score(y_test, y_pred)
                mse = mean_squared_error(y_test, y_pred)
            mean_abs_err = mean_absolute_error(y_test, y_pred)
            self.logger.info(f"[Classification] Model: {model_name} - Accuracy: {accuracy*100:.4f}%")
            self.logger.info(f"[Regression] Model: {model_name} - MSE: {mse:.4f}")
            print(f"Model: {model_name} - Accuracy: {accuracy*100:.4f}%")
            if save_results:
                results = pd.DataFrame({"Model": [model_name], "Type": [model_type], "Accuracy": [accuracy], "MSE": [mse], "Classification Report": [classifi_report], "Mean Absolute Error": [mean_abs_err]})
                results.to_csv(results_path + results_name, index=False)
                self.logger.info(f"Results saved at: {results_path + results_name}")
                return results
            return {'accuracy_score':accuracy,'mean_squared_error' : mse,'classification_report':classifi_report,'mean_absolute_error':mean_abs_err}
        except Exception as e:
            self.logger.error(f"Error in evaluate_model: {e}", exc_info=True)
            raise
        
    def feature_scaling(self, feature, scaler_type="standard"):
        """
        Apply feature scaling to the training and testing data.
        Parameters
        ----------
        feature : array-like
            Training data.
        X_test : array-like
        Testing data.
        scaler_type : str, optional
        Type of scaler to use. Can be "standard" (default) or "minmax".
        Returns
        -------
        X_ train_scaled : array-like
        Scaled training data.
        X_test_scaled : array-like
        Scaled testing data.
        Raises
        ------
        TypeError
        If `scaler_type` is not "standard" or "minmax".
        Exception
        Any exception raised during scaling is logged and re-raised.
        """
        try:
            if scaler_type not in ["standard", "minmax"]:
                raise TypeError("scaler_type must be 'standard' or 'minmax'.")
            if scaler_type == "standard":
                scaler = StandardScaler()
            else:
                scaler = MinMaxScaler()
            feature_scaled = scaler.fit_transform(feature)
            return feature_scaled
        except Exception as e:
            self.logger.error(f"Error in feature_scaling: {e}", exc_info=True)
            raise