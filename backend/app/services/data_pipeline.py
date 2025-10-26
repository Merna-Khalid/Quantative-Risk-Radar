import pandas as pd
import numpy as np
import yfinance as yf
from fredapi import Fred
from app.core.cache import get_cached_data, set_cached_data
import os
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Optional, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


fred = None

def initialize_fred_client():
    global fred
    api_key = os.getenv("FRED_API_KEY")

    if not api_key:
        logger.critical("FRED_API_KEY missing in environment!")
        return None

    try:
        fred = Fred(api_key=api_key)
        logger.info("✅ FRED client initialized.")
        return fred
    except Exception as e:
        logger.critical(f"Failed to initialize FRED client: {e}")
        fred = None
        return None

def validate_data_quality(df: pd.DataFrame, min_rows: int = 100, max_null_pct: float = 0.1) -> Dict[str, Any]:
    """Validate data quality and return validation results."""
    validation = {
        'is_valid': True,
        'issues': [],
        'summary': {}
    }
    
    if df.empty:
        validation['is_valid'] = False
        validation['issues'].append("DataFrame is empty")
        return validation
    
    validation['summary']['total_rows'] = len(df)
    validation['summary']['total_columns'] = len(df.columns)
    validation['summary']['date_range'] = {
        'start': str(df.index.min()) if not df.empty else None,
        'end': str(df.index.max()) if not df.empty else None
    }
    
    # Check minimum rows
    if len(df) < min_rows:
        validation['is_valid'] = False
        validation['issues'].append(f"Insufficient data: only {len(df)} rows, minimum {min_rows} required")
    
    # Check for null values
    null_pct = df.isnull().sum().sum() / (len(df) * len(df.columns))
    validation['summary']['null_percentage'] = null_pct
    
    if null_pct > max_null_pct:
        validation['issues'].append(f"High null percentage: {null_pct:.2%} exceeds threshold {max_null_pct:.2%}")
    
    # Check for infinite values
    inf_count = np.isinf(df.select_dtypes(include=[np.number])).sum().sum()
    validation['summary']['infinite_values'] = inf_count
    if inf_count > 0:
        validation['issues'].append(f"Found {inf_count} infinite values")
    
    return validation

async def get_oil_data(force_refresh: bool = False) -> pd.DataFrame:
    """Fetch oil price data (WTI crude) with caching."""
    cache_key = "oil_data"
    
    if not force_refresh:
        try:
            cached_data = await get_cached_data(cache_key)
            if cached_data is not None:
                logger.info("Loaded oil data from cache")
                validation = validate_data_quality(cached_data, min_rows=10)
                if validation['is_valid']:
                    return cached_data
        except Exception as e:
            logger.warning(f"Error loading cached oil data: {e}")
    
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = '2003-01-01'
        
        logger.info(f"Downloading oil data from {start_date} to {end_date}")
        
        # WTI Crude Oil futures (CL=F) and US Oil Fund (USO) as fallback
        oil_tickers = ['CL=F', 'USO', 'BZ=F']  # WTI, US Oil Fund, Brent
        
        oil_data = yf.download(oil_tickers, start=start_date, end=end_date, progress=False, auto_adjust=True)['Close']
        
        if oil_data.empty:
            logger.warning("No oil data from yfinance, trying FRED")
            # Fallback to FRED WTI crude price
            try:
                wti_data = fred.get_series('DCOILWTICO', start=start_date, end=end_date)
                if not wti_data.empty:
                    oil_data = pd.DataFrame({'WTI': wti_data})
                    logger.info(f"Loaded WTI data from FRED: {len(oil_data)} rows")
                else:
                    raise ValueError("No oil data available")
            except Exception as e:
                logger.warning(f"FRED oil data also failed: {e}")
                raise
        
        # Calculate returns
        oil_returns = oil_data.pct_change().dropna() * 100
        
        # Use the first available column as primary oil return
        if len(oil_returns.columns) > 0:
            primary_oil_col = oil_returns.columns[0]
            oil_df = pd.DataFrame({
                'oil_price': oil_data[primary_oil_col],
                'oil_return': oil_returns[primary_oil_col]
            })
        else:
            raise ValueError("No valid oil data columns")
        
        # Cache results
        if not oil_df.empty:
            await set_cached_data(cache_key, oil_df, expire_seconds=3600)
            logger.info(f"Cached oil data with {len(oil_df)} rows")
        
        return oil_df
        
    except Exception as e:
        logger.error(f"Error fetching oil data: {e}")
        # Return empty but properly formatted DataFrame
        return pd.DataFrame(columns=['oil_price', 'oil_return'])

async def get_fx_data(force_refresh: bool = False) -> pd.DataFrame:
    """Fetch FX data (DXY and major currency pairs) with caching."""
    cache_key = "fx_data"
    
    if not force_refresh:
        try:
            cached_data = await get_cached_data(cache_key)
            if cached_data is not None:
                logger.info("Loaded FX data from cache")
                validation = validate_data_quality(cached_data, min_rows=10)
                if validation['is_valid']:
                    return cached_data
        except Exception as e:
            logger.warning(f"Error loading cached FX data: {e}")
    
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = '2003-01-01'
        
        logger.info(f"Downloading FX data from {start_date} to {end_date}")
        
        # FX tickers: DXY (USD Index), EUR/USD, USD/JPY
        fx_tickers = ['DX-Y.NYB', 'EURUSD=X', 'JPY=X', 'GBPUSD=X']  # DXY, EUR/USD, USD/JPY, GBP/USD
        
        fx_data = yf.download(fx_tickers, start=start_date, end=end_date, progress=False, auto_adjust=True)['Close']
        
        if fx_data.empty:
            logger.warning("No FX data from yfinance, trying FRED")
            # Fallback to FRED DXY data
            try:
                dxy_data = fred.get_series('DTWEXBGS', start=start_date, end=end_date)  # Broad Dollar Index
                if not dxy_data.empty:
                    fx_data = pd.DataFrame({'DXY': dxy_data})
                    logger.info(f"Loaded DXY data from FRED: {len(fx_data)} rows")
                else:
                    raise ValueError("No FX data available")
            except Exception as e:
                logger.warning(f"FRED FX data also failed: {e}")
                raise
        
        # Rename columns for clarity
        fx_data = fx_data.rename(columns={
            'DX-Y.NYB': 'DXY',
            'EURUSD=X': 'EURUSD',
            'JPY=X': 'USDJPY', 
            'GBPUSD=X': 'GBPUSD'
        })
        
        # Calculate returns (for DXY, positive return = USD strengthening)
        fx_returns = fx_data.pct_change().dropna() * 100
        
        fx_df = pd.DataFrame()
        
        # Use DXY as primary FX indicator if available
        if 'DXY' in fx_returns.columns:
            fx_df['dxy_return'] = fx_returns['DXY']
            fx_df['fx_change'] = fx_returns['DXY']  # Primary FX change metric
        elif 'EURUSD' in fx_returns.columns:
            # Use EUR/USD inverse as USD strength proxy
            fx_df['fx_change'] = -fx_returns['EURUSD']  # EUR/USD down = USD up
        else:
            # Use first available column
            first_col = fx_returns.columns[0]
            fx_df['fx_change'] = fx_returns[first_col]
        
        # Add individual currency returns if available
        for col in ['EURUSD', 'USDJPY', 'GBPUSD']:
            if col in fx_returns.columns:
                fx_df[f'{col.lower()}_return'] = fx_returns[col]
        
        # Cache results
        if not fx_df.empty:
            await set_cached_data(cache_key, fx_df, expire_seconds=3600)
            logger.info(f"Cached FX data with {len(fx_df)} rows")
        
        return fx_df
        
    except Exception as e:
        logger.error(f"Error fetching FX data: {e}")
        # Return empty but properly formatted DataFrame
        return pd.DataFrame(columns=['fx_change', 'dxy_return'])

async def get_credit_signals(force_refresh: bool = False, _internal_call: bool = False) -> pd.DataFrame:
    """Fetch credit signals with oil and FX data integration."""

    if _internal_call:
        force_refresh = False 

    cache_key = "credit_signals"
    
    # Try to get from cache first (unless force refresh)
    if not force_refresh:
        try:
            cached_data = await get_cached_data(cache_key)
            if cached_data is not None:
                logger.info("Loaded credit signals from cache")
                validation = validate_data_quality(cached_data)
                if validation['is_valid']:
                    return cached_data
                else:
                    logger.warning("Cached credit signals failed validation, refreshing...")
        except Exception as e:
            logger.warning(f"Error loading cached credit signals: {e}")
    
    # Fetch fresh data
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = '2003-01-01'
        
        logger.info(f"Downloading credit data from {start_date} to {end_date}")
        etf_tickers = ['HYG', 'TLT', 'LQD', 'SPY']
        etf_prices = yf.download(etf_tickers, start=start_date, end=end_date, progress=False, auto_adjust=True)['Close']
        
        if etf_prices.empty:
            raise ValueError("No ETF data downloaded")
            
        # Calculate credit ratio
        if 'HYG' in etf_prices.columns and 'TLT' in etf_prices.columns:
            credit_ratio = np.log(etf_prices["HYG"] / etf_prices["TLT"])
            credit_signal = (credit_ratio - credit_ratio.mean()) / credit_ratio.std()
            credit_signal = credit_signal.rolling(20).mean()
            credit_signal.name = 'credit_ratio_signal'
        else:
            logger.warning("HYG or TLT not available for credit ratio")
            credit_signal = pd.Series(0, index=etf_prices.index, name='credit_ratio_signal')

        # Calculate returns
        credit_returns = etf_prices.pct_change().dropna() * 100

        logger.info(f"Downloaded {len(credit_returns)} rows of credit returns")

        # Economic indicators with fallback
        econ_series = {
            'HY_Spread': 'BAMLH0A0HYM2',
            'IG_Spread': 'BAMLC0A0CM', 
            'VIX': 'VIXCLS',
            'Unemployment': 'UNRATE',
            'Term_Spread': 'T10Y2Y'
        }
        
        fred_data = {}
        successful_fred = 0
        for name, series_id in econ_series.items():
            try:
                series_data = fred.get_series(series_id, start=start_date, end=end_date)
                if not series_data.empty:
                    fred_data[name] = series_data
                    successful_fred += 1
                    logger.debug(f"Successfully fetched FRED series: {name}")
                else:
                    logger.warning(f"No data for FRED series: {series_id}")
            except Exception as e:
                logger.warning(f"Error fetching FRED series {series_id}: {e}")
        
        logger.info(f"Successfully fetched {successful_fred}/{len(econ_series)} FRED series")
        
        all_data = credit_returns.copy()
        
        # Add FRED data if available
        if fred_data:
            fred_df = pd.DataFrame(fred_data)
            fred_daily = fred_df.reindex(credit_returns.index).ffill().dropna()
            if not fred_daily.empty:
                fred_changes = fred_daily.pct_change() * 100
                fred_changes.columns = [f"{col}_Change" for col in fred_changes.columns]
                
                all_data = pd.concat([all_data, fred_changes], axis=1)
        
        # Fetch oil and FX data concurrently
        oil_task = asyncio.create_task(get_oil_data(force_refresh))
        fx_task = asyncio.create_task(get_fx_data(force_refresh))
        
        oil_data, fx_data = await asyncio.gather(oil_task, fx_task)
        
        # Merge oil data
        if not oil_data.empty:
            oil_aligned = oil_data.reindex(all_data.index).ffill().dropna()
            if not oil_aligned.empty:
                all_data['oil_return'] = oil_aligned['oil_return']
                all_data['oil_price'] = oil_aligned['oil_price']
                logger.info(f"Added oil data: {len(oil_aligned)} rows")
        
        # Merge FX data  
        if not fx_data.empty:
            fx_aligned = fx_data.reindex(all_data.index).ffill().dropna()
            if not fx_aligned.empty:
                all_data['fx_change'] = fx_aligned['fx_change']
                if 'dxy_return' in fx_aligned.columns:
                    all_data['dxy_return'] = fx_aligned['dxy_return']
                logger.info(f"Added FX data: {len(fx_aligned)} rows")
        
        all_data = all_data.replace([np.inf, -np.inf], np.nan).ffill().dropna()
        
        # Final validation
        validation = validate_data_quality(all_data, min_rows=50)
        if not validation['is_valid']:
            logger.error(f"Credit signals validation failed: {validation['issues']}")
        
        if not all_data.empty:
            await set_cached_data(cache_key, all_data, expire_seconds=3600)

        logger.info(f"Returning credit signals with {len(all_data)} rows and {len(all_data.columns)} columns")
        logger.info(f"Available columns: {list(all_data.columns)}")
        return all_data
        
    except Exception as e:
        logger.error(f"Critical error in get_credit_signals: {e}")
        # Try to return cached data even if it's stale
        try:
            cached_data = await get_cached_data(cache_key)
            if cached_data is not None:
                logger.warning("Returning stale cached data due to API failure")
                return cached_data
        except:
            pass
            
        logger.error("No data available - returning empty DataFrame")
        return pd.DataFrame()

async def get_sector_data(force_refresh: bool = False) -> pd.DataFrame:
    """Downloads and caches daily returns for sector ETFs."""
    cache_key = "sector_data"
    
    if not force_refresh:
        try:
            cached_data = await get_cached_data(cache_key)
            if cached_data is not None:
                logger.info("Loaded sector data from cache")
                validation = validate_data_quality(cached_data)
                if validation['is_valid']:
                    return cached_data
                else:
                    logger.warning("Cached sector data failed validation, refreshing...")
        except Exception as e:
            logger.warning(f"Error loading cached sector data: {e}")
    
    try:
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = '2003-01-01'
        
        sector_tickers = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY", "SPY"]
        
        logger.info(f"Downloading sector data from {start_date} to {end_date}")
        prices = yf.download(sector_tickers, start=start_date, end=end_date, progress=False, auto_adjust=True)["Close"]
        
        if prices.empty:
            raise ValueError("No sector data downloaded from Yahoo Finance")
            
        rets = prices.pct_change().dropna() * 100
        logger.info(f"Downloaded {len(rets)} rows of sector returns")

        validation = validate_data_quality(rets, min_rows=50)
        if not validation['is_valid']:
            logger.error(f"Sector data validation failed: {validation['issues']}")
        
        if not rets.empty:
            await set_cached_data(cache_key, rets, expire_seconds=3600)

        return rets
        
    except Exception as e:
        logger.error(f"Critical error in get_sector_data: {e}")
        try:
            cached_data = await get_cached_data(cache_key)
            if cached_data is not None:
                logger.warning("Returning stale cached sector data due to API failure")
                return cached_data
        except:
            pass
            
        logger.error("No sector data available - returning empty DataFrame")
        return pd.DataFrame()

async def get_full_market_dataset(force_refresh: bool = False, _internal_call: bool = False) -> pd.DataFrame:
    """Returns combined sector + credit + macro dataset with oil and FX data."""

    if _internal_call:
        force_refresh = False
        
    cache_key = "full_market_data"
    
    if not force_refresh:
        try:
            cached_data = await get_cached_data(cache_key)
            if cached_data is not None:
                logger.info("Loaded full market dataset from cache")
                validation = validate_data_quality(cached_data)
                if validation['is_valid']:
                    return cached_data
                else:
                    logger.warning("Cached full dataset failed validation, refreshing...")
        except Exception as e:
            logger.warning(f"Error loading cached full dataset: {e}")
    
    try:
        credit_task = asyncio.create_task(get_credit_signals(force_refresh))
        sector_task = asyncio.create_task(get_sector_data(force_refresh))

        credit_data, sector_data = await asyncio.gather(credit_task, sector_task)
        
        if credit_data.empty and sector_data.empty:
            logger.error("Both credit and sector data sources returned empty results")
            return pd.DataFrame()
        elif credit_data.empty:
            logger.warning("Credit data empty, returning sector data only")
            return sector_data
        elif sector_data.empty:
            logger.warning("Sector data empty, returning credit data only")
            return credit_data
        
        logger.info(f"Sector data shape: {sector_data.shape}")
        logger.info(f"Credit data shape: {credit_data.shape}")
        logger.info(f"Credit columns: {list(credit_data.columns)}")
        
        has_oil = 'oil_return' in credit_data.columns
        has_fx = 'fx_change' in credit_data.columns
        
        logger.info(f"Oil data available: {has_oil}, FX data available: {has_fx}")
        
        overlapping_cols = set(sector_data.columns) & set(credit_data.columns)
        if overlapping_cols:
            logger.info(f"Found overlapping columns: {overlapping_cols}")
        
        merged = sector_data.join(credit_data, how="outer", rsuffix="_credit")
        
        logger.info(f"After outer join (before ffill): {len(merged)} rows")
        
        merged = merged.ffill().dropna()
        
        logger.info(f"After ffill + dropna: {len(merged)} rows")
        
        # Remove columns with suffix
        suffix_cols = [col for col in merged.columns if col.endswith('_credit')]
        if suffix_cols:
            logger.info(f"Dropping suffixed columns: {suffix_cols}")
            merged = merged.drop(columns=suffix_cols)
        
        validation = validate_data_quality(merged)
        if not validation['is_valid']:
            logger.warning(f"Merged dataset has issues: {validation['issues']}")
        
        if merged.empty:
            logger.error("No data available after merging")
            return pd.DataFrame()

        if not merged.empty:
            merged = merged.replace([np.inf, -np.inf], np.nan)
            merged = merged.bfill()
            merged = merged.ffill()
            merged = merged.fillna(0)
            await set_cached_data(cache_key, merged, expire_seconds=3600)

        logger.info(f"Returning full market dataset with {len(merged)} rows and {len(merged.columns)} columns")
        logger.info(f"Final columns: {list(merged.columns)}")
        return merged
        
    except Exception as e:
        logger.error(f"Error in get_full_market_dataset: {e}")
        try:
            cached_data = await get_cached_data(cache_key)
            if cached_data is not None:
                logger.warning("Returning stale cached full dataset due to merge failure")
                return cached_data
        except:
            pass
            
        return pd.DataFrame()

async def debug_signal_generation():
    """Debug function to check signal generation"""
    try:
        full_df = await get_full_market_dataset(force_refresh=True)
        print(f"Full dataset shape: {full_df.shape}")
        print(f"Full dataset columns: {list(full_df.columns)}")
        
        required_columns = ['SPY', 'XLK', 'XLF', 'HYG']
        missing_columns = [col for col in required_columns if col not in full_df.columns]
        print(f"Missing required columns: {missing_columns}")
        
        # Check if we have data for HAR and DCC calculations
        if 'SPY' in full_df.columns:
            spy_returns = full_df['SPY'].pct_change().dropna()
            print(f"SPY returns available: {len(spy_returns)}")
            
            # Test HAR calculation
            realized_vol = spy_returns.rolling(window=21).std()
            daily_vol = spy_returns.rolling(window=1).std()
            weekly_vol = spy_returns.rolling(window=5).std()
            monthly_vol = spy_returns.rolling(window=21).std()
            
            har_forecast = (daily_vol + weekly_vol + monthly_vol) / 3
            excess_vol = realized_vol - har_forecast
            
            if not excess_vol.dropna().empty:
                har_z = (excess_vol - excess_vol.mean()) / excess_vol.std()
                print(f"HAR excess vol z-score latest: {har_z.iloc[-1]}")
            else:
                print("HAR calculation failed - no excess vol data")
        
        # Test DCC calculation
        if 'XLK' in full_df.columns and 'XLF' in full_df.columns:
            xlk_returns = full_df['XLK'].pct_change().dropna()
            xlf_returns = full_df['XLF'].pct_change().dropna()
            
            common_idx = xlk_returns.index.intersection(xlf_returns.index)
            if len(common_idx) > 0:
                rolling_corr = xlk_returns.rolling(window=21).corr(xlf_returns)
                print(f"DCC correlation latest: {rolling_corr.iloc[-1]}")
            else:
                print("DCC calculation failed - no common dates")
                
    except Exception as e:
        print(f"Debug failed: {e}")

# Run this to debug
if __name__ == "__main__":
    import asyncio
    asyncio.run(debug_signal_generation())