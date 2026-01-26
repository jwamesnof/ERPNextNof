"""Page Object Models for ERPNext UI."""
from playwright.sync_api import Page, expect
import logging

logger = logging.getLogger(__name__)


class LoginPage:
    """Page Object for ERPNext login page."""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def navigate(self):
        """Navigate to login page."""
        self.page.goto(f"{self.base_url}/login")

    def login(self, username: str, password: str):
        """Perform login."""
        logger.info(f"Logging in as {username}")
        
        # Wait for login form
        self.page.wait_for_selector('input[name="usr"]', timeout=10000)
        
        # Fill credentials
        self.page.fill('input[name="usr"]', username)
        self.page.fill('input[name="pwd"]', password)
        
        # Click login button
        self.page.click('button:has-text("Login")')
        
        # Wait for successful login (desk page loads)
        self.page.wait_for_url("**/app/home", timeout=15000)
        logger.info("Login successful")


class SalesOrderListPage:
    """Page Object for Sales Order list page."""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def navigate(self):
        """Navigate to Sales Order list."""
        self.page.goto(f"{self.base_url}/app/sales-order")
        self.page.wait_for_load_state("networkidle")

    def create_new(self):
        """Click 'New' button to create Sales Order."""
        self.page.click('button:has-text("New")')
        self.page.wait_for_load_state("networkidle")


class SalesOrderPage:
    """Page Object for Sales Order form page."""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url

    def fill_customer(self, customer: str):
        """Fill customer field."""
        logger.info(f"Filling customer: {customer}")
        
        # Click customer field
        self.page.click('[data-fieldname="customer"] input')
        self.page.fill('[data-fieldname="customer"] input', customer)
        
        # Select from dropdown
        self.page.wait_for_selector(f'li.awesomplete:has-text("{customer}")', timeout=5000)
        self.page.click(f'li.awesomplete:has-text("{customer}")')

    def add_item(self, item_code: str, qty: float):
        """Add an item to the Sales Order."""
        logger.info(f"Adding item: {item_code}, qty: {qty}")
        
        # Click 'Add Row' button in items table
        self.page.click('[data-fieldname="items"] button:has-text("Add Row")')
        
        # Fill item code in the last row
        self.page.click('[data-fieldname="items"] [data-fieldname="item_code"] input:last-of-type')
        self.page.fill('[data-fieldname="items"] [data-fieldname="item_code"] input:last-of-type', item_code)
        
        # Select from dropdown
        self.page.wait_for_selector(f'li.awesomplete:has-text("{item_code}")', timeout=5000)
        self.page.click(f'li.awesomplete:has-text("{item_code}")')
        
        # Fill quantity
        self.page.fill('[data-fieldname="items"] [data-fieldname="qty"] input:last-of-type', str(qty))

    def save(self):
        """Save the Sales Order."""
        logger.info("Saving Sales Order")
        self.page.click('button:has-text("Save")')
        self.page.wait_for_selector('.indicator-pill:has-text("Draft")', timeout=10000)

    def get_name(self) -> str:
        """Get the Sales Order ID after save."""
        # ERPNext shows doc name in title bar
        title = self.page.title()
        # Format: "SO-00001 - Sales Order"
        so_id = title.split(" - ")[0].strip() if " - " in title else ""
        logger.info(f"Sales Order created: {so_id}")
        return so_id

    def get_custom_field_value(self, field_name: str) -> str:
        """Get value of a custom field."""
        try:
            value = self.page.input_value(f'[data-fieldname="{field_name}"] input')
            return value
        except Exception as e:
            logger.warning(f"Could not read custom field {field_name}: {e}")
            return ""

    def has_comment_with_text(self, text: str) -> bool:
        """Check if a comment containing text exists."""
        try:
            # Click comments tab
            self.page.click('a:has-text("Comments")')
            self.page.wait_for_timeout(1000)
            
            # Check for comment text
            comment = self.page.locator(f'.comment-content:has-text("{text}")')
            return comment.count() > 0
        except Exception as e:
            logger.warning(f"Could not check comments: {e}")
            return False

    def reload(self):
        """Reload the current page."""
        self.page.reload()
        self.page.wait_for_load_state("networkidle")
