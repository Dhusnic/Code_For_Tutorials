import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy import stats

# Advanced Data Creation
def create_complex_dataset():
    np.random.seed(42)
    dates = pd.date_range(start='2023-01-01', periods=1000)
    
    return pd.DataFrame({
        'date': dates,
        'sales': np.random.normal(1000, 100, 1000),
        'customers': np.random.poisson(30, 1000),
        'category': np.random.choice(['A', 'B', 'C', 'D'], 1000),
        'region': np.random.choice(['North', 'South', 'East', 'West'], 1000),
        'promotion': np.random.choice([0, 1], 1000),
        'satisfaction': np.random.uniform(1, 5, 1000)
    })

# Complex Data Transformation
def calculate_metrics(df):
    df['sales_per_customer'] = df['sales'] / df['customers']
    df['sales_zscore'] = stats.zscore(df['sales'])
    df['rolling_avg_sales'] = df['sales'].rolling(window=7).mean()
    df['sales_momentum'] = df['sales'].pct_change()
    df['peak_sales'] = df.groupby('category')['sales'].transform('max')
    return df

# Advanced Time Series Analysis
def time_series_features(df):
    df['year'] = df['date'].dt.year
    df['month'] = df['date'].dt.month
    df['day_of_week'] = df['date'].dt.dayofweek
    df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
    
    # Seasonal Decomposition
    df['sales_MA'] = df['sales'].rolling(window=30).mean()
    df['sales_volatility'] = df['sales'].rolling(window=30).std()
    return df

# Complex Aggregations
def advanced_aggregations(df):
    return df.groupby(['category', 'region']).agg({
        'sales': ['mean', 'std', 'min', 'max'],
        'customers': ['mean', 'count'],
        'satisfaction': ['mean', 'median'],
        'sales_per_customer': 'mean',
        'promotion': 'sum'
    }).round(2)

# Statistical Analysis
def statistical_analysis(df):
    results = {}
    
    # Correlation Matrix
    results['correlation'] = df[['sales', 'customers', 'satisfaction']].corr()
    
    # Chi-Square Test
    contingency = pd.crosstab(df['category'], df['region'])
    results['chi_square'] = stats.chi2_contingency(contingency)
    
    # T-Test for Promotions
    promo_sales = df[df['promotion'] == 1]['sales']
    non_promo_sales = df[df['promotion'] == 0]['sales']
    results['ttest'] = stats.ttest_ind(promo_sales, non_promo_sales)
    
    return results

# Advanced Visualization
def create_advanced_plots(df):
    # Sales Distribution by Category
    plt.figure(figsize=(12, 6))
    for category in df['category'].unique():
        plt.hist(df[df['category'] == category]['sales'], 
                alpha=0.5, 
                label=category)
    plt.title('Sales Distribution by Category')
    plt.legend()
    plt.savefig('sales_distribution.png')
    plt.close()
    
    # Time Series Plot
    plt.figure(figsize=(15, 7))
    plt.plot(df['date'], df['sales'], label='Daily Sales')
    plt.plot(df['date'], df['rolling_avg_sales'], label='7-day Moving Average')
    plt.title('Sales Time Series with Moving Average')
    plt.legend()
    plt.savefig('sales_timeseries.png')
    plt.close()

# Main execution
if __name__ == "__main__":
    # Create dataset
    df = create_complex_dataset()
    
    # Apply transformations
    df = calculate_metrics(df)
    df = time_series_features(df)
    
    # Generate insights
    aggregations = advanced_aggregations(df)
    stats_results = statistical_analysis(df)
    
    # Create visualizations
    create_advanced_plots(df)
    
    # Export results
    df.to_csv('complex_dataset.csv', index=False)
    aggregations.to_csv('aggregated_results.csv')
    
    # Print summary statistics
    print("\nDataset Shape:", df.shape)
    print("\nCorrelation Matrix:")
    print(stats_results['correlation'].round(3))
    print("\nPromotion T-Test p-value:", stats_results['ttest'].pvalue)