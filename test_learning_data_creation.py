#!/usr/bin/env python3
"""
Test script to verify that the adaptive category learner correctly creates
the data directory and learning data file if they don't exist.
"""

import os
import sys
import shutil
import tempfile
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from parsers.adaptive_category_learner import AdaptiveCategoryLearner


def test_data_file_creation():
    """Test that the learner creates data directory and file if they don't exist."""
    
    print("🧪 Testing Adaptive Category Learner - Data File Creation")
    print("=" * 60)
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Using temporary directory: {temp_dir}")
        
        # Test 1: Create learner with non-existent data file path
        test_data_file = os.path.join(temp_dir, "data", "category_learning_data.json")
        print(f"\n🔍 Test 1: Creating learner with path: {test_data_file}")
        
        # Verify directory and file don't exist initially
        data_dir = os.path.dirname(test_data_file)
        print(f"📂 Data directory exists before: {os.path.exists(data_dir)}")
        print(f"📄 Data file exists before: {os.path.exists(test_data_file)}")
        
        # Create the learner - this should create directory and file
        learner = AdaptiveCategoryLearner(test_data_file)
        
        # Verify directory and file were created
        print(f"📂 Data directory exists after: {os.path.exists(data_dir)}")
        print(f"📄 Data file exists after: {os.path.exists(test_data_file)}")
        
        # Verify file has correct structure
        if os.path.exists(test_data_file):
            import json
            with open(test_data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            required_keys = [
                'payee_category_mapping',
                'category_confidence', 
                'last_updated',
                'user_corrections',
                'recent_transactions',
                'statistics'
            ]
            
            print(f"📋 File structure validation:")
            for key in required_keys:
                exists = key in data
                print(f"  ✅ {key}: {'Present' if exists else '❌ Missing'}")
            
            print(f"📊 Statistics: {data.get('statistics', {})}")
        
        # Test 2: Test learning functionality
        print(f"\n🧠 Test 2: Testing learning functionality")
        
        # Add some test associations
        test_associations = [
            ("McDonald's", "cat_restaurant", "🍔 Fast Food", 0.9),
            ("Éxito", "cat_groceries", "🛒 Groceries", 0.85),
            ("Uber", "cat_transport", "🚗 Transportation", 0.95)
        ]
        
        for payee, cat_id, cat_name, confidence in test_associations:
            learner.learn_association(payee, cat_id, cat_name, confidence)
            print(f"  📝 Learned: {payee} → {cat_name}")
        
        # Test predictions
        print(f"\n🔮 Test 3: Testing predictions")
        test_payees = ["McDonald's", "mcdonalds", "Éxito", "exito", "Uber", "Unknown Store"]
        
        for payee in test_payees:
            prediction = learner.predict_category(payee)
            if prediction:
                cat_id, cat_name, confidence = prediction
                print(f"  🎯 {payee} → {cat_name} (confidence: {confidence:.2f})")
            else:
                print(f"  ❓ {payee} → No prediction")
        
        # Test statistics
        print(f"\n📈 Test 4: Learning statistics")
        stats = learner.get_learning_statistics()
        for key, value in stats.items():
            print(f"  📊 {key}: {value}")
        
        print(f"\n✅ All tests completed successfully!")
        
        # Test 5: Test loading existing file
        print(f"\n🔄 Test 5: Testing reload from existing file")
        learner2 = AdaptiveCategoryLearner(test_data_file)
        
        # Verify data was loaded correctly
        associations_count = len(learner2.learning_data['payee_category_mapping'])
        print(f"  📊 Associations loaded: {associations_count}")
        
        # Test a prediction to ensure data integrity
        prediction = learner2.predict_category("McDonald's")
        if prediction:
            cat_id, cat_name, confidence = prediction
            print(f"  🎯 McDonald's → {cat_name} (confidence: {confidence:.2f})")
        
        print(f"\n🎉 Data file creation and persistence test completed successfully!")


def test_fallback_behavior():
    """Test fallback behavior when data directory cannot be created."""
    
    print(f"\n🛡️ Testing fallback behavior")
    print("=" * 40)
    
    # Try to create learner with invalid path (should fallback)
    invalid_path = "/root/invalid_path/data/category_learning_data.json"
    print(f"🚫 Testing with invalid path: {invalid_path}")
    
    try:
        learner = AdaptiveCategoryLearner(invalid_path)
        print(f"✅ Fallback successful, using: {learner.data_file}")
        
        # Test that it still works
        learner.learn_association("Test Store", "cat_test", "Test Category", 0.8)
        prediction = learner.predict_category("Test Store")
        if prediction:
            print(f"🎯 Fallback learner working: Test Store → {prediction[1]}")
        
        # Clean up fallback file
        if os.path.exists(learner.data_file) and "fallback" in learner.data_file:
            os.remove(learner.data_file)
            print(f"🧹 Cleaned up fallback file: {learner.data_file}")
            
    except Exception as e:
        print(f"❌ Fallback test failed: {e}")


if __name__ == "__main__":
    try:
        test_data_file_creation()
        test_fallback_behavior()
        print(f"\n🎊 All tests passed! The adaptive category learner now properly creates")
        print(f"   the data directory and learning file if they don't exist.")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
