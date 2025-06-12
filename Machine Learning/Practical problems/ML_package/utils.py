import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import logging
import joblib
from sklearn.metrics import (
        accuracy_score, precision_score, recall_score, f1_score,
        confusion_matrix, classification_report,
        r2_score, mean_squared_error, mean_absolute_error
    )
from sklearn.preprocessing import StandardScaler,MinMaxScaler
from dotenv import load_dotenv
from pathlib import Path
import os
import torch
# from tensorflow import keras
# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


class ML_Utils:
    """
    A base class for performing basic feature correlation analysis
    and data visualization in machine learning workflows.
    """
    
    none_list = ["None", [], {}, [""], ""]

    def __init__(self):
        """
        Initialize the ML_Base_Controller and configure the logger.
        """
        # Load .env from another directory (e.g., ../config/.env)
        env_path = Path(__file__).resolve().parent.parent / "settings" / ".env"
        load_dotenv(dotenv_path=env_path)
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
        
    def plot_loss_curve(self,losses):
        """
        Plot the training loss curve over epochs.
        Parameters
        ----------
        losses : list or array-like
            A sequence of loss values recorded during training (one per epoch).
            
        logger : logging.Logger, optional
            Optional logger instance to record plotting activity and errors.
        Returns
        -------
        None
        Raises
        ------
        ValueError
            If losses is not a non-empty list or array-like object.
        """
        try:
            if not losses or not isinstance(losses, (list, tuple)):
                raise ValueError("Input 'losses' must be a non-empty list or tuple.")
            plt.figure(figsize=(8, 5))
            plt.plot(range(1, len(losses) + 1), losses, marker='o', linestyle='-', color='b')
            plt.title('Training Loss Over Epochs')
            plt.xlabel('Epoch')
            plt.ylabel('Loss')
            plt.grid(True)
            plt.tight_layout()
            plt.show()
            if self.logger:
                self.logger.info("Successfully plotted loss curve.")
        except Exception as e:
            error_msg = f"Error in plot_loss_curve: {e}"
            if self.logger:
                self.logger.error(error_msg, exc_info=True)
            else:
                print(error_msg)
            raise
        
    def save_ML_model_to_path(self, model, file_name, save_dir=""):
        """
        Save a trained machine learning model to the specified path using joblib.
        Parameters
        ----------
        model : object
            Trained model object to be saved.
        file_name : str
            File name for the saved model (e.g., 'model.pkl').
        save_dir : str, optional
            Subdirectory inside MODEL_SAVE_DIR to save the model. If empty, only MODEL_SAVE_DIR is used.
        Returns
        -------
        str
            Full path where the model was saved.
        Raises
        ------
        ValueError
            If `file_name` is not a string or environment variable is missing.
        Exception
            Any other error during saving is logged and re-raised.
        """
        try:
            if not isinstance(file_name, str) or not isinstance(save_dir, str):
                raise ValueError("Both 'file_name' and 'save_dir' must be strings.")

            base_dir = os.getenv("MODEL_SAVE_DIR")
            if not base_dir:
                raise EnvironmentError("Environment variable 'MODEL_SAVE_DIR' is not set.")

            # Construct final path
            full_path = os.path.join(base_dir, save_dir) if save_dir not in self.none_list else base_dir

            os.makedirs(full_path, exist_ok=True)

            full_file_path = os.path.join(full_path, file_name)

            joblib.dump(model, full_file_path)

            if self.logger:
                self.logger.info(f"Model saved successfully at: {full_file_path}")
            else:
                print(f"Model saved at: {full_file_path}")

            return full_file_path

        except Exception as e:
            error_msg = f"Failed to save model: {e}"
            if self.logger:
                self.logger.error(error_msg, exc_info=True)
            else:
                print(error_msg)
            raise   
    
    def load_ML_model_from_path(self, file_name, load_dir=""):
        """
        Load a trained machine learning model from the specified path using joblib.
        Parameters
        ----------
        file_name : str
            File name of the saved model (e.g., 'model.pkl').
        load_dir : str, optional
            Subdirectory within the base MODEL_SAVE_DIR to load the model from.
        Returns
        -------
        object
            The loaded model object.
        Raises
        ------
        ValueError
            If `file_name` or `load_dir` is not a string.
        FileNotFoundError
            If the model file does not exist.
        Exception
            Any error during loading is logged and re-raised.
        """
        try:
            if not isinstance(file_name, str) or not isinstance(load_dir, str):
                raise ValueError("Both 'file_name' and 'load_dir' must be strings.")

            base_dir = os.getenv("MODEL_SAVE_DIR")
            if not base_dir:
                raise EnvironmentError("Environment variable 'MODEL_SAVE_DIR' is not set.")

            full_path = base_dir
            if load_dir not in self.none_list:
                full_path = os.path.join(base_dir, load_dir)

            full_path = os.path.join(full_path, file_name)

            if not os.path.exists(full_path):
                raise FileNotFoundError(f"Model file not found at: {full_path}")

            model = joblib.load(full_path)

            if self.logger:
                self.logger.info(f"Model loaded successfully from: {full_path}")
            else:
                print(f"Model loaded from: {full_path}")

            return model

        except Exception as e:
            error_msg = f"Failed to load model: {e}"
            if self.logger:
                self.logger.error(error_msg, exc_info=True)
            else:
                print(error_msg)
            raise
        
    def save_Dl_model_to_path(self, model, file_name, save_dir="", framework="pytorch"):
        """
        Save a trained deep learning model to the specified path.

        Parameters
        ----------
        model : object
            Trained model (PyTorch or Keras model).
        file_name : str
            File name to save the model (e.g., 'model.pth' or 'model.h5').
        save_dir : str, optional
            Subdirectory within MODEL_SAVE_DIR to save the model.
        framework : str, default "pytorch"
            Type of framework: "pytorch" or "keras".

        Returns
        -------
        str
            Full path where the model is saved.

        Raises
        ------
        ValueError
            If inputs are invalid.
        Exception
            For unexpected errors (logged and re-raised).
        """
        try:
            if not isinstance(file_name, str) or not isinstance(save_dir, str):
                raise ValueError("file_name and save_dir must be strings.")
            if framework not in ["pytorch", "keras"]:
                raise ValueError("framework must be either 'pytorch' or 'keras'.")

            base_dir = os.getenv("MODEL_SAVE_DIR")
            if not base_dir:
                raise EnvironmentError("Environment variable 'MODEL_SAVE_DIR' not set.")

            full_path = os.path.join(base_dir, save_dir) if save_dir not in self.none_list else base_dir
            os.makedirs(full_path, exist_ok=True)
            # full_file_path = os.path.join(full_path, file_name)
            if framework == "pytorch":
                if "." in file_name and file_name.split(".")[-1]:
                    file_name = file_name.replace(".",".pth")
                elif "." not in file_name:
                    file_name = file_name+".pth"
                full_file_path = os.path.join(full_path, file_name)
                torch.save(model.state_dict(), full_file_path)
            elif framework == "keras":
                if "." in file_name and file_name.split(".")[-1]:
                    file_name = file_name.replace(".",".keras")
                elif "." not in file_name:
                    file_name = file_name+".keras"
                full_file_path = os.path.join(full_path, file_name)
                model.save(full_file_path)

            self.logger.info(f"DL model saved at: {full_file_path}") if self.logger else print(f"Saved at: {full_file_path}")
            return full_file_path

        except Exception as e:
            msg = f"Error saving DL model: {e}"
            self.logger.error(msg, exc_info=True) if self.logger else print(msg)
            raise
        
    def load_Dl_model_from_path(self, file_name, model_class=None, load_dir="", framework="pytorch"):
        """
        Load a saved deep learning model from disk.
        Parameters
        ----------
        file_name : str
            File name of the model (e.g., 'model.pth' or 'model.h5').
        model_class : class, optional (required for PyTorch)
            The model class (with the same architecture) to load weights into.
        load_dir : str, optional
            Subdirectory in MODEL_SAVE_DIR where the model is stored.
        framework : str, default "pytorch"
            "pytorch" or "keras".
        Returns
        -------
        model : object
            Loaded model instance.
        Raises
        ------
        ValueError
            If inputs are invalid.
        FileNotFoundError
            If model file doesn't exist.
        Exception
            On unexpected errors.
        """
        try:
            if not isinstance(file_name, str) or not isinstance(load_dir, str):
                raise ValueError("file_name and load_dir must be strings.")
            if framework not in ["pytorch", "keras"]:
                raise ValueError("framework must be either 'pytorch' or 'keras'.")

            base_dir = os.getenv("MODEL_SAVE_DIR")
            if not base_dir:
                raise EnvironmentError("Environment variable 'MODEL_SAVE_DIR' not set.")

            full_path = os.path.join(base_dir, load_dir) if load_dir not in self.none_list else base_dir
            full_file_path = os.path.join(full_path, file_name)

            if not os.path.exists(full_file_path):
                raise FileNotFoundError(f"Model not found at {full_file_path}")

            if framework == "pytorch":
                if model_class is None:
                    raise ValueError("model_class must be provided for PyTorch models.")
                model = model_class()
                model.load_state_dict(torch.load(full_file_path))
                model.eval()
            # elif framework == "keras":
            #     model = keras.models.load_model(full_file_path)
            self.logger.info(f"DL model loaded from: {full_file_path}") if self.logger else print(f"Loaded from: {full_file_path}")
            return model
        except Exception as e:
            msg = f"Error loading DL model: {e}"
            self.logger.error(msg, exc_info=True) if self.logger else print(msg)
            raise




    def evaluate_model(self, y_test, y_pred, model=None, confusion_matrix_plot=False,
                   model_name="GenericModel", model_type="", save_results=False,
                   results_path="", results_name=""):
        """
        Universal evaluator for any ML or DL model (classification or regression).

        Parameters
        ----------
        y_test : array-like
            True labels.
        y_pred : array-like
            Predicted labels or probabilities/logits (processed before passing).
        model : object, optional
            The model object. Can be scikit-learn, XGBoost, PyTorch, etc.
        confusion_matrix_plot : bool
            Plot confusion matrix if classification.
        model_name : str
            Name of the model.
        model_type : str
            Classifier, Regressor or left blank (auto-detects).
        save_results : bool
            Save metrics to a CSV.
        results_path : str
            Directory path to save results.
        results_name : str
            Filename of CSV.

        Returns
        -------
        dict : metrics
            Dictionary of evaluation results.
        """
        try:
            y_test = np.array(y_test)
            y_pred = np.array(y_pred)

            # Auto-detect binary classification if y_test has only 2 values
            is_classification = False
            if model_type.lower() == "classifier" or (
                model is not None and (hasattr(model, "predict_proba") or hasattr(model, "classes_"))
            ) or len(np.unique(y_test)) <= 2:
                is_classification = True
            elif model_type.lower() == "regressor":
                is_classification = False

            metrics = {}

            if is_classification:
                if y_pred.ndim > 1 and y_pred.shape[1] > 1:
                    # Multi-class predicted labels
                    y_pred = np.argmax(y_pred, axis=1)
                elif y_pred.ndim > 1 and y_pred.shape[1] == 1:
                    y_pred = (y_pred > 0.5).astype(int).flatten()
                elif y_pred.ndim == 1 and np.any((y_pred > 0) & (y_pred < 1)):
                    # Sigmoid or probabilities in 1D
                    y_pred = (y_pred > 0.5).astype(int)

                acc = accuracy_score(y_test, y_pred)
                # prec = precision_score(y_test, y_pred, zero_division=0)
                # rec = recall_score(y_test, y_pred, zero_division=0)
                # f1 = f1_score(y_test, y_pred, zero_division=0)
                prec = precision_score(y_test, y_pred, average='weighted', zero_division=0)
                rec = recall_score(y_test, y_pred, average='weighted', zero_division=0)
                f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0)
                mse = mean_squared_error(y_test, y_pred)
                mae = mean_absolute_error(y_test, y_pred)
                report_dict = classification_report(y_test, y_pred, output_dict=True)
                report_str = classification_report(y_test, y_pred)

                metrics.update({
                    "type": "Classifier",
                    "accuracy": acc,
                    "precision": prec,
                    "recall": rec,
                    "f1_score": f1,
                    "mean_squared_error": mse,
                    "mean_absolute_error": mae,
                    "classification_report_dict": report_dict,
                    "classification_report": report_str
                })

                if confusion_matrix_plot:
                    cm = confusion_matrix(y_test, y_pred)
                    plt.figure(figsize=(6, 4))
                    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
                    plt.title(f"{model_name} - Confusion Matrix")
                    plt.xlabel("Predicted")
                    plt.ylabel("Actual")
                    plt.tight_layout()
                    plt.show()

            else:
                r2 = r2_score(y_test, y_pred)
                mse = mean_squared_error(y_test, y_pred)
                mae = mean_absolute_error(y_test, y_pred)

                metrics.update({
                    "type": "Regressor",
                    "r2_score": r2,
                    "mean_squared_error": mse,
                    "mean_absolute_error": mae
                })

            # Logging
            self.logger.info(f"Evaluation - {model_name}")
            for k, v in metrics.items():
                if not isinstance(v, dict):
                    self.logger.info(f"{k}: {v}")

            # Save results
            if save_results:
                base_dir = os.getenv("RESULT_SAVE_DIR")
                if not base_dir:
                    raise EnvironmentError("Environment variable 'RESULT_SAVE_DIR' not set.")
                if results_name in self.none_list:
                    raise ValueError("Invalid results_name value.")
                if results_path not in self.none_list:
                    os.makedirs(results_path, exist_ok=True)
                    results_file = os.path.join(base_dir,results_path, results_name)
                else:
                    results_file = os.path.join(base_dir,results_name)
                row = {
                    "Model": model_name,
                    "Type": metrics["type"]
                }
                for k, v in metrics.items():
                    if not isinstance(v, dict):
                        row[k.replace("_", " ").title()] = v
                df = pd.DataFrame([row])
                df.to_csv(results_file, index=False)
                self.logger.info(f"Saved evaluation results to {results_file}")

            return metrics

        except Exception as e:
            self.logger.error(f"Error in evaluate_model: {e}", exc_info=True)
            raise





    # def evaluate_model(self, y_test, y_pred, model, confusion_matrix_plot=False,
    #                model_name="", model_type="", save_results=False,
    #                results_path="", results_name=""):
    #     """
    #     Evaluate the performance of a trained model and optionally save the results.
        
    #     Parameters
    #     ----------
    #     y_test : array-like
    #         True labels for the test data.
    #     y_pred : array-like
    #         Predicted labels from the model.
    #     model : object
    #         An initialized ML model (classifier or regressor).
    #     confusion_matrix_plot : bool
    #         If True, displays a confusion matrix (only for classification).
    #     model_name : str
    #         Name of the model (used in logs and saved results).
    #     model_type : str
    #         Type of model (e.g., "Classifier" or "Regressor").
    #     save_results : bool
    #         If True, saves evaluation metrics to CSV.
    #     results_path : str
    #         Directory path where results will be saved.
    #     results_name : str
    #         File name of the saved CSV file.
            
    #     Returns
    #     -------
    #     dict
    #         Evaluation metrics.
    #     """
    #     try:
    #         # Type checks
    #         if not all(isinstance(arg, str) for arg in [model_name, model_type, results_path, results_name]):
    #             raise TypeError("model_name, model_type, results_path, and results_name must all be strings.")
    #         if not isinstance(save_results, bool):
    #             raise TypeError("save_results must be a boolean.")

    #         self.logger.info(f"Evaluating model: {model_name}")

    #         metrics = {}
    #         is_classifier = hasattr(model, "predict_proba") or hasattr(model, "classes_")

    #         if is_classifier:
    #             accuracy = accuracy_score(y_test, y_pred)
    #             mse = mean_squared_error(y_test, y_pred)
    #             mae = mean_absolute_error(y_test, y_pred)
    #             cls_report = classification_report(y_test, y_pred, output_dict=False)

    #             self.logger.info(f"[Classification] {model_name} - Accuracy: {accuracy:.4f}")
    #             self.logger.info(f"[Classification] {model_name} - MSE: {mse:.4f}")
    #             self.logger.info(f"[Classification] {model_name} - MAE: {mae:.4f}")

    #             if confusion_matrix_plot:
    #                 cm = confusion_matrix(y_test, y_pred)
    #                 sns.heatmap(cm, annot=True, fmt='d', cmap='Blues')
    #                 plt.title("Confusion Matrix")
    #                 plt.xlabel("Predicted")
    #                 plt.ylabel("Actual")
    #                 plt.tight_layout()
    #                 plt.show()

    #             metrics = {
    #                 "accuracy_score": accuracy,
    #                 "mean_squared_error": mse,
    #                 "mean_absolute_error": mae,
    #                 "classification_report": cls_report
    #             }
    #         else:
    #             # Regression case
    #             r2 = r2_score(y_test, y_pred)
    #             mse = mean_squared_error(y_test, y_pred)
    #             mae = mean_absolute_error(y_test, y_pred)

    #             self.logger.info(f"[Regression] {model_name} - R2 Score: {r2:.4f}")
    #             self.logger.info(f"[Regression] {model_name} - MSE: {mse:.4f}")
    #             self.logger.info(f"[Regression] {model_name} - MAE: {mae:.4f}")

    #             metrics = {
    #                 "r2_score": r2,
    #                 "mean_squared_error": mse,
    #                 "mean_absolute_error": mae
    #             }

    #         # Save results
    #         if save_results:
    #             df = pd.DataFrame([{
    #                 "Model": model_name,
    #                 "Type": model_type,
    #                 **{k.replace("_", " ").title(): v for k, v in metrics.items() if k != "classification_report"},
    #                 "Classification Report": metrics.get("classification_report", "")
    #             }])
    #             full_path = results_path.rstrip("/") + "/" + results_name
    #             df.to_csv(full_path, index=False)
    #             self.logger.info(f"Results saved at: {full_path}")

    #         return metrics

    #     except Exception as e:
    #         self.logger.error(f"Error in evaluate_model: {e}", exc_info=True)
    #         raise

    #def evaluate_model(self, y_test, y_pred,model,confusion_matrix_plot=False, model_name="", model_type="", save_results=False, results_path="", results_name=""):
    #     """
    #     Evaluate the performance of a trained model and optionally save the results.
    #     Parameters
    #     ----------
    #     y_test : array-like
    #         True labels for the test data.

    #     y_pred : array-like
    #         Predicted labels from the model.

    #     model : object
    #         An initialized machine learning model object that implements `predict`.
        
    #     model_name : str, optional
    #         A label for the model, used for logging and print statements. Default is "".

    #     model_type : str, optional
    #         A label for the model type, used for logging and print statements. Default is "".

    #     save_results : bool, optional
    #         If True, saves the evaluation results using `pandas`. Default is False.

    #     results_path : str, optional
    #         The directory path to save the results (used only if `save_results` is True).

    #     results_name : str, optional
    #         The filename (with or without extension) used to save the results. Combined with `results_ path`. 
    #         Raises
    #         ------
    #         TypeError
    #         If `model_name`, `model_type`, `results_path`, or `results_name` is not a string, or if `save_results` is not a bool.
    #     Exception
    #     Any exception raised during evaluation and saving is logged and re-raised.
    #     """
    #     try:
    #         if not isinstance(model_name, str):
    #             raise TypeError("model_ name must be a string.")
    #         if not isinstance(model_type, str):
    #             raise TypeError("model_type must be a string.")
    #         if not isinstance(save_results, bool):
    #             raise TypeError("save_results must be a boolean.")
    #         if not isinstance(results_path, str):
    #             raise TypeError("results_path must be a string.")
    #         if not isinstance(results_name, str):
    #             raise TypeError("results_name must be a string.")
    #         self.logger.info(f"Evaluating model: {model_name}")
    #         # Determine if it's a classifier or regressor
    #         if hasattr(model, "predict_proba") or hasattr(model, "classes_"):
    #             accuracy = accuracy_score(y_test, y_pred)
    #             mse=mean_squared_error(y_test, y_pred)
    #             classifi_report = classification_report(y_test, y_pred)
    #             self.logger.info(f"[Classification] Model: {model_name} - Accuracy: {accuracy*100:.4f}%")
    #             if confusion_matrix_plot:
    #                 sns.heatmap(confusion_matrix(y_test, y_pred), annot=True, fmt='d')
    #                 plt.xlabel("Predicted")
    #                 plt.ylabel("True Label")
    #                 plt.title("Confusion Matrix")
    #                 plt.xticks(rotation=45)
    #                 plt.yticks(rotation=0)
    #                 plt.tight_layout()
    #                 plt.show()
    #         else:
    #             accuracy = r2_score(y_test, y_pred)
    #             mse = mean_squared_error(y_test, y_pred)
    #         mean_abs_err = mean_absolute_error(y_test, y_pred)
    #         self.logger.info(f"[Classification] Model: {model_name} - Accuracy: {accuracy*100:.4f}%")
    #         self.logger.info(f"[Regression] Model: {model_name} - MSE: {mse:.4f}")
    #         print(f"Model: {model_name} - Accuracy: {accuracy*100:.4f}%")
    #         if save_results:
    #             results = pd.DataFrame({"Model": [model_name], "Type": [model_type], "Accuracy": [accuracy], "MSE": [mse], "Classification Report": [classifi_report], "Mean Absolute Error": [mean_abs_err]})
    #             results.to_csv(results_path + results_name, index=False)
    #             self.logger.info(f"Results saved at: {results_path + results_name}")
    #             return results
    #         return {'accuracy_score':accuracy,'mean_squared_error' : mse,'classification_report':classifi_report,'mean_absolute_error':mean_abs_err}
    #     except Exception as e:
    #         self.logger.error(f"Error in evaluate_model: {e}", exc_info=True)
    #         raise