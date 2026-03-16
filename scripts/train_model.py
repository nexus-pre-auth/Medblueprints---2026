"""
Train Approval Prediction Model
================================
Loads all labeled outcomes from the database and trains the
GradientBoosting approval prediction model.

Run after seeding:
    python scripts/seed_training_data.py
    python scripts/train_model.py

Or retrain after new real outcomes are recorded:
    python scripts/train_model.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.outcome_dataset import OutcomeDataset
from src.engines.approval_prediction import ApprovalPredictionEngine


async def main():
    print("Loading labeled outcomes from database...")
    dataset = OutcomeDataset()
    await dataset.init()

    labeled = await dataset.load_labeled()
    print(f"Found {len(labeled)} labeled outcomes.")

    if len(labeled) < 10:
        print("ERROR: Need at least 10 labeled outcomes. Run seed_training_data.py first.")
        sys.exit(1)

    approved   = sum(1 for o in labeled if o.approval_result == "approved")
    rejected   = sum(1 for o in labeled if o.approval_result == "rejected")
    conditional = sum(1 for o in labeled if o.approval_result == "conditional")
    print(f"  Approved: {approved}  Conditional: {conditional}  Rejected: {rejected}")

    print("\nTraining GradientBoosting model...")
    engine = ApprovalPredictionEngine()
    result = engine.train(labeled)

    print(f"\nModel trained successfully!")
    print(f"  Training samples : {result['training_samples']}")
    print(f"  Approval rate    : {result['approval_rate']*100:.1f}%")
    print(f"  Model saved to   : {result['model_path']}")
    print("\nThe API will now use the trained model instead of heuristics.")


if __name__ == "__main__":
    asyncio.run(main())
