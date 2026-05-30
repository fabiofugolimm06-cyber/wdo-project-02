from abc import ABC, abstractmethod
import pandas as pd

class StrategyBase(ABC):
    def __init__(self, name: str, params: dict = None):
        self.name = name
        self.params = params if params else {}
    
    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        pass
    
    def get_description(self) -> str:
        return f"{self.name} (params: {self.params})"
