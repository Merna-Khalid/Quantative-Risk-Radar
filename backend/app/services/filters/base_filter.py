from abc import ABC, abstractmethod

class BaseFilter(ABC):
    @abstractmethod
    def apply(self, signal):
        pass
