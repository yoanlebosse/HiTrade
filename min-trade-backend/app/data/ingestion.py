import pandas as pd
import re
from typing import List, Optional
from pathlib import Path
from ..models.fund import Fund, AssetClass, FundMetrics


class DataIngestion:
    STANDARD_ISIN_PREFIXES = {'FR', 'LU', 'IE', 'BE', 'DE', 'AT', 'GB', 'NL', 'XS', 'LI', 'SC'}
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._raw_data: Optional[pd.DataFrame] = None
        self._funds: List[Fund] = []
    
    def load_data(self) -> pd.DataFrame:
        self._raw_data = pd.read_excel(self.file_path)
        return self._raw_data
    
    def normalize_and_parse(self) -> List[Fund]:
        if self._raw_data is None:
            self.load_data()
        
        funds = []
        for _, row in self._raw_data.iterrows():
            fund = self._parse_row(row)
            if fund:
                funds.append(fund)
        
        self._funds = funds
        return funds
    
    def _parse_row(self, row: pd.Series) -> Optional[Fund]:
        try:
            isin = str(row.get('CODE ISIN', '')).strip()
            name = str(row.get('Nom du fonds', '')).strip()
            
            if not isin or not name or isin == 'nan':
                return None
            
            sri = int(row.get('SRI', 4))
            if sri < 1:
                sri = 1
            elif sri > 7:
                sri = 7
            
            management_company = str(row.get('Société de gestion', '')).strip()
            if management_company == 'nan':
                management_company = None
            
            description = str(row.get('Descriptif', '')).strip()
            if description == 'nan':
                description = None
            else:
                description = self._clean_html(description)
            
            platforms_str = str(row.get('Disponible chez', '')).strip()
            platforms = []
            if platforms_str and platforms_str != 'nan':
                platforms = [p.strip() for p in platforms_str.split(';') if p.strip()]
            
            label = str(row.get('LABELL', '')).strip()
            if label == 'nan':
                label = None
            
            is_standard = self._is_standard_isin(isin)
            asset_class = self._determine_asset_class(label, description, name)
            
            return Fund(
                isin=isin,
                name=name,
                management_company=management_company,
                sri=sri,
                asset_class=asset_class,
                description=description,
                available_platforms=platforms,
                is_standard_isin=is_standard,
                label=label,
                metrics=None,
                fundamental_score=None,
                top_week_score=None
            )
        except Exception as e:
            print(f"Error parsing row: {e}")
            return None
    
    def _is_standard_isin(self, isin: str) -> bool:
        if len(isin) < 2:
            return False
        prefix = isin[:2].upper()
        return prefix in self.STANDARD_ISIN_PREFIXES
    
    def _clean_html(self, text: str) -> str:
        clean = re.sub(r'<[^>]+>', '', text)
        clean = re.sub(r'\s+', ' ', clean)
        return clean.strip()
    
    def _determine_asset_class(self, label: Optional[str], description: Optional[str], name: str) -> AssetClass:
        text = f"{label or ''} {description or ''} {name}".lower()
        
        if 'fond' in text and 'euro' in text:
            return AssetClass.FONDS_EUROS
        if any(kw in text for kw in ['immobilier', 'scpi', 'opci', 'pierre']):
            return AssetClass.IMMOBILIER
        if any(kw in text for kw in ['action', 'equity', 'stock', 'cap.']):
            return AssetClass.ACTIONS
        if any(kw in text for kw in ['obligation', 'bond', 'taux', 'fixed income', 'crédit']):
            return AssetClass.OBLIGATIONS
        if any(kw in text for kw in ['monétaire', 'money market', 'liquidité']):
            return AssetClass.MONETAIRE
        if any(kw in text for kw in ['diversifié', 'mixte', 'flexible', 'allocation']):
            return AssetClass.DIVERSIFIE
        
        return AssetClass.AUTRES
    
    @property
    def funds(self) -> List[Fund]:
        return self._funds
    
    def get_standard_isin_funds(self) -> List[Fund]:
        return [f for f in self._funds if f.is_standard_isin]
    
    def get_special_funds(self) -> List[Fund]:
        return [f for f in self._funds if not f.is_standard_isin]
