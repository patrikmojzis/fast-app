import importlib
import inspect
from pathlib import Path

from fast_app.decorators import register_observer, register_policy


# TODO: Add support for custom models_dir, observers_dir, policies_dir
def autodiscover_models() -> None:
    """
    Autodiscover models and registers their corresponding observers and policies.
    
    Example of naming conventions:
    ```
    - Model: app/models/user.py -> class User
    - Observer: app/observers/user_observer.py -> class UserObserver
    - Policy: app/policies/user_policy.py -> class UserPolicy
    ```

    Args:
        models_dir: The directory containing the models.
        observers_dir: The directory containing the observers.
        policies_dir: The directory containing the policies.
    """
    from fast_app import Model, Observer, Policy

    models_dir = Path("app/models")
    
    if not models_dir.exists():
        print(f"📁 No {models_dir} directory found, skipping autodiscovery")
        return
        
    print(f"🔍 Starting model autodiscovery in {models_dir}...")
    
    # Define discovery mappings for better performance
    discovery_config = [
        ("observers", "Observer", Observer, register_observer),
        ("policies", "Policy", Policy, register_policy)
    ]
    
    discovered_count = 0
    
    # Get all Python model files at once
    model_files = [f for f in models_dir.glob("*.py") if not f.name.startswith("__")]
    
    for model_file in model_files:
        model_name = model_file.stem
        module_path = f"app.models.{model_name}"
        
        try:
            # Import model module and find Model classes
            model_module = importlib.import_module(module_path)
            model_classes = [
                (name, cls) for name, cls in inspect.getmembers(model_module, inspect.isclass)
                if (issubclass(cls, Model) and 
                    cls != Model and 
                    cls.__module__ == module_path)
            ]
            
            for class_name, model_cls in model_classes:
                discovered_count += 1
                print(f"📋 Found model: {class_name}")
                
                # Try to discover and register observer/policy for each model
                for folder, suffix, base_class, decorator in discovery_config:
                    target_class_name = f"{class_name}{suffix}"
                    target_module_path = f"app.{folder}.{model_name}_{suffix.lower()}"
                    
                    try:
                        target_module = importlib.import_module(target_module_path)
                        if (hasattr(target_module, target_class_name) and 
                            inspect.isclass(target_cls := getattr(target_module, target_class_name)) and
                            issubclass(target_cls, base_class)):
                            
                            decorator(target_cls)(model_cls)
                            print(f"✅ Auto-registered {target_class_name} for {class_name}")
                            
                    except ImportError:
                        # Silently ignore missing files - this is expected
                        pass
                    
        except ImportError:
            # Silently ignore missing files - this is expected
            pass
    
    if discovered_count > 0:
        print(f"🎉 Autodiscovery completed! Found {discovered_count} model(s)")