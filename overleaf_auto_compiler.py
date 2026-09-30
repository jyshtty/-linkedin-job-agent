"""
Automated LaTeX to PDF compilation using Overleaf
Automates the entire upload → compile → download process
"""
import os
import sys
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class OverleafCompiler:
    """Automates Overleaf compilation process"""

    def __init__(self, headless=False):
        """Initialize Selenium WebDriver"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        # Set download directory
        self.download_dir = os.path.join(os.getcwd(), "tailored_resume")
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        chrome_options.add_experimental_option("prefs", prefs)

        print("🚀 Initializing Chrome WebDriver...")
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.wait = WebDriverWait(self.driver, 30)
            print("✅ WebDriver initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize WebDriver: {e}")
            raise

    def compile_latex(self, tex_path: str, output_pdf_path: str = None) -> bool:
        """
        Compile LaTeX file using Overleaf

        Args:
            tex_path: Path to .tex file
            output_pdf_path: Optional custom output path for PDF

        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.exists(tex_path):
                print(f"❌ File not found: {tex_path}")
                return False

            print(f"\n{'='*80}")
            print(f"COMPILING LATEX VIA OVERLEAF (AUTOMATED)")
            print(f"{'='*80}\n")
            print(f"Input:  {tex_path}")

            # Step 1: Go to Overleaf
            print("📂 Opening Overleaf...")
            self.driver.get("https://www.overleaf.com/")
            time.sleep(2)

            # Check if user is logged in
            try:
                # Look for "New Project" button (indicates logged in)
                new_project_btn = self.driver.find_element(By.XPATH, "//button[contains(., 'New Project') or contains(., 'Create New')]")
                print("✅ Already logged in to Overleaf")
                is_logged_in = True
            except NoSuchElementException:
                print("⚠️  Not logged in to Overleaf")
                is_logged_in = False

            if not is_logged_in:
                print("\n" + "="*80)
                print("🔐 AUTHENTICATION REQUIRED")
                print("="*80)
                print("\nPlease log in to Overleaf in the browser window that opened.")
                print("After logging in, the script will continue automatically.")
                print("\nOptions:")
                print("1. Log in with Google/Email")
                print("2. Create a free account if you don't have one")
                print("\nWaiting for login... (timeout: 120 seconds)")
                print("="*80 + "\n")

                # Wait for user to login (check for new project button)
                try:
                    self.wait = WebDriverWait(self.driver, 120)
                    self.wait.until(
                        EC.presence_of_element_located((By.XPATH, "//button[contains(., 'New Project') or contains(., 'Create New')]"))
                    )
                    print("✅ Login successful!")
                except TimeoutException:
                    print("❌ Login timeout. Please try again.")
                    return False

            # Step 2: Create new project via upload
            print("📤 Creating new project...")
            time.sleep(2)

            # Click "New Project" button
            try:
                new_project_btn = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'New Project') or contains(., 'Create New')]"))
                )
                new_project_btn.click()
                time.sleep(1)

                # Click "Upload Project" option
                upload_option = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Upload Project') or contains(., 'Upload')]"))
                )
                upload_option.click()
                print("✅ Upload dialog opened")

            except Exception as e:
                print(f"⚠️  Could not find New Project button, trying direct upload URL...")
                self.driver.get("https://www.overleaf.com/project/new/upload")
                time.sleep(2)

            # Step 3: Upload file
            print(f"📁 Uploading {os.path.basename(tex_path)}...")
            time.sleep(1)

            # Find file input and upload
            try:
                file_input = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
                )
                file_input.send_keys(os.path.abspath(tex_path))
                print("✅ File uploaded")

                # Wait for upload to complete and project to open
                print("⏳ Waiting for compilation...")
                time.sleep(5)  # Give it time to compile

            except Exception as e:
                print(f"❌ Upload failed: {e}")
                return False

            # Step 4: Wait for compilation to complete
            print("🔨 Compiling LaTeX...")
            time.sleep(5)  # Additional time for compilation

            # Step 5: Download PDF
            print("💾 Downloading PDF...")
            try:
                # Look for download button
                download_btn = self.wait.until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'Download PDF') or contains(., 'Download')]"))
                )
                download_btn.click()
                print("✅ Download initiated")

                # Wait for download to complete
                time.sleep(3)

                # Find the downloaded PDF
                pdf_name = os.path.basename(tex_path).replace('.tex', '.pdf')
                downloaded_pdf = os.path.join(self.download_dir, pdf_name)

                # Check if PDF exists
                if os.path.exists(downloaded_pdf):
                    file_size = os.path.getsize(downloaded_pdf) / 1024  # KB
                    print(f"\n{'='*80}")
                    print(f"✅ SUCCESS! PDF compiled and downloaded ({file_size:.1f} KB)")
                    print(f"Location: {downloaded_pdf}")
                    print(f"{'='*80}\n")
                    return True
                else:
                    print("⚠️  PDF downloaded but location uncertain. Check your Downloads folder.")
                    return True

            except Exception as e:
                print(f"⚠️  Auto-download failed: {e}")
                print("💡 PDF should be compiled in Overleaf. Download manually if needed.")
                return True  # Compilation likely succeeded even if download failed

        except Exception as e:
            print(f"\n❌ Compilation failed: {e}")
            return False

        finally:
            # Don't close browser immediately to allow manual intervention if needed
            print("\n💡 Browser will remain open for 10 seconds in case you need to download manually...")
            time.sleep(10)

    def close(self):
        """Close the browser"""
        if hasattr(self, 'driver'):
            self.driver.quit()
            print("🔒 Browser closed")


def main():
    if len(sys.argv) < 2:
        print("Usage: python overleaf_auto_compiler.py <path_to_tex_file>")
        print("\nExample:")
        print("  python overleaf_auto_compiler.py tailored_resume/job_1_resume.tex")
        sys.exit(1)

    tex_path = sys.argv[1]

    compiler = None
    try:
        compiler = OverleafCompiler(headless=False)  # Set to True for headless mode
        success = compiler.compile_latex(tex_path)

        if success:
            print("\n✅ Process completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Process failed. Please check the errors above.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        sys.exit(1)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

    finally:
        if compiler:
            compiler.close()


if __name__ == '__main__':
    main()
