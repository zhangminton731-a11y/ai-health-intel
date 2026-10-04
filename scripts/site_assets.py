"""Keep immutable browser code cacheable independently of daily data."""
import hashlib
import re


def extract_assets(page, site):
    assets = site/'assets'; assets.mkdir(parents=True, exist_ok=True)
    def save(content, extension):
        name = 'site.'+hashlib.sha256(content.encode()).hexdigest()[:16]+'.'+extension
        (assets/name).write_text(content, encoding='utf-8')
        return 'assets/'+name
    page = re.sub(r'<style>(.*?)</style>', lambda m:'<link rel="stylesheet" href="'+save(m[1],'css')+'">', page, flags=re.S)
    # The tiny theme initializer stays inline to avoid a first-frame flash.
    page = re.sub(r'<script>\s*(\(\(\)=>\{.*?</script>)',
                  lambda m:'<script defer src="'+save(m[1][:-9].strip(),'js')+'"></script>', page, flags=re.S)
    return page
