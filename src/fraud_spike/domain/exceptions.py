class FraudSpikeError(Exception):
    """Base class for every domain error this service raises."""

class ModelNotLoadedError(FraudSpikeError):
    pass

class FeatureComputationError(FraudSpikeError):
    def __init__(self, uid: str, cause: Exception):
        self.uid, self.cause = uid, cause
        super().__init__(f"Failed to compute features for uid={uid}: {cause}")
