"""
product_filters.py - Filters for product catalog
"""

class ProductFilters:
    """Filters for product catalog focusing on notebooks and smartphones"""
    
    @staticmethod
    def filter_notebooks(products, min_specs=True):
        """
        Filter notebooks from product catalog
        
        Args:
            products (list): List of Product objects
            min_specs (bool): Whether to filter for minimum specs (i3, 4GB RAM)
            
        Returns:
            list: Filtered list of notebook products
        """
        notebooks = [p for p in products if p.category.lower() == 'notebook']
        
        # Filter for preferred brands
        preferred_brands = [p for p in notebooks if any(
            brand.lower() in p.name.lower() or brand.lower() in p.description.lower() 
            for brand in ['asus', 'acer']
        )]
        
        # If we have preferred brands, prioritize them
        if preferred_brands:
            notebooks = preferred_brands
        
        # Apply minimum specs filter if requested
        if min_specs:
            min_spec_notebooks = []
            for notebook in notebooks:
                desc_lower = notebook.description.lower()
                
                # Check for processor (i3 or better)
                has_min_processor = any(
                    proc in desc_lower for proc in 
                    ['i3', 'i5', 'i7', 'i9', 'ryzen 3', 'ryzen 5', 'ryzen 7', 'ryzen 9']
                )
                
                # Check for RAM (4GB or more)
                has_min_ram = any(
                    ram in desc_lower for ram in 
                    ['4gb', '4 gb', '6gb', '6 gb', '8gb', '8 gb', '12gb', '12 gb', '16gb', '16 gb', '32gb', '32 gb']
                )
                
                if has_min_processor and has_min_ram:
                    min_spec_notebooks.append(notebook)
            
            # If we found notebooks meeting minimum specs, use those
            if min_spec_notebooks:
                return min_spec_notebooks
        
        return notebooks
    
    @staticmethod
    def filter_smartphones(products):
        """
        Filter smartphones from product catalog
        
        Args:
            products (list): List of Product objects
            
        Returns:
            list: Filtered list of smartphone products
        """
        return [p for p in products if p.category.lower() in ['smartphone', 'celular', 'telefone']]
    
    @staticmethod
    def get_recommended_products(products, user_message):
        """
        Get recommended products based on user message
        
        Args:
            products (list): List of Product objects
            user_message (str): User message to analyze
            
        Returns:
            list: List of recommended products
        """
        user_message = user_message.lower()
        
        # Check for notebook keywords
        if any(keyword in user_message for keyword in ['notebook', 'laptop', 'computador', 'pc']):
            return ProductFilters.filter_notebooks(products)
        
        # Check for smartphone keywords
        if any(keyword in user_message for keyword in ['celular', 'smartphone', 'telefone', 'iphone', 'samsung']):
            return ProductFilters.filter_smartphones(products)
        
        # If no specific category detected, return both notebooks and smartphones
        notebooks = ProductFilters.filter_notebooks(products)
        smartphones = ProductFilters.filter_smartphones(products)
        
        # Limit total recommendations to 10 products
        combined = notebooks + smartphones
        return combined[:10]
