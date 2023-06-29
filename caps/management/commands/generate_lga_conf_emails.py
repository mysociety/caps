from html import escape
from os.path import join

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template import Template, Context

from tqdm import tqdm

from caps.models import Council

file_header = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="p-3 p-lg-4 bg-light border-bottom position-sticky" style="top: 0;">
        <label for="q" class="form-label">Filter councils by name</label>
        <input type="search" class="form-control" id="q">
    </div>
    <div class="p-3 p-lg-4">
"""

file_footer = """
    </div>
    <script>
    document.querySelector('#q').addEventListener('keyup', function(e){
        var q = this.value.toLowerCase();
        if ( q == '' ) {
            document.querySelectorAll('section.d-none').forEach(function(el){
                el.classList.remove('d-none');
            });
        } else {
            document.querySelectorAll('section').forEach(function(el){
                var councilName = el.querySelector('h1').textContent.toLowerCase();
                var shouldBeHidden = (councilName.indexOf(q) == -1);
                el.classList.toggle('d-none', shouldBeHidden);
            });
        }
    });
    document.querySelectorAll('section .form-control').forEach(function(el){
        el.addEventListener('click', function(e){
            this.select();
        });
    });
    </script>
</body>
</html>
"""

email_template = Template(
    """
<p>Hi NAME,</p>
<p>You probably already know that the council most similar to yours in terms of emissions, deprivation and rural/urban factor is {{ twin.name }}.</p>
{% with n=twin.plan_overlap.just_in_b %}<p>But do you know which {% if n|length > 1 %}{{ n|length }} {% endif %}{{ n|pluralize:"topic appears,topics appear" }} in their climate plans and {{ n|pluralize:"doesn’t appear,don’t appear" }} in yours?</p>{% endwith %}
<p>…We do! I’m the climate lead at <a href="https://www.mysociety.org"><u>mySociety</u></a>, a charity building free digital tools that enable local authorities to reach their net zero goals. Our topic-based council comparisons are just the latest feature we’ve added, and I’d love to get your feedback on it.</p>
<p><a href="https://calendly.com/zarino-mysociety/lga-conference"><u>Book a 15 minute chat with me at the conference next week</u></a>, or stop by stand T10A, and I’ll give you a demo. Hopefully you’ll also come away with some useful insights to share with your own teams at {{ council.name }}.</p>
<p>Thank you so much, I really appreciate your time.</p>
<p><strong>Zarino Zappia</strong><br>Climate Programme Lead, mySociety<br>mysociety.org</p>
<p>PS. This winter we’ll also be working with a few pilot councils on a <a href="https://www.mysociety.org/tag/neighbourhood-warmth/"><u>community-led approach to domestic retrofit</u></a>. I know incentivising domestic decarbonisation is a big challenge for local authorities – happy to share more when we meet!</p>"""
)


class Command(BaseCommand):
    help = "generates HTML for one email per local authority, ready to copy-paste into the LGA conference message editor"

    def handle(self, *args, **options):
        html_filepath = join(settings.MEDIA_ROOT, "data", "lga_conf_emails.html")
        with open(html_filepath, "w") as f:
            f.writelines(file_header)

            for council in tqdm(Council.current_councils()):
                tqdm.write(f"Generating email for {council.name}")

                context = {"council": council}

                related_councils = council.get_related_councils()
                related_councils_intersection = (
                    council.related_council_keyphrase_intersection()
                )
                for group in related_councils:
                    for c in group["councils"]:
                        c.plan_overlap = related_councils_intersection[c]
                    if group["type"].slug == "composite":
                        context["twin"] = group["councils"][0]

                email_html = email_template.render(Context(context))
                escaped_email_text = escape(email_html)

                if (
                    "twin" in context
                    and len(context["twin"].plan_overlap.just_in_b) > 0
                ):
                    f.writelines("<section class='mb-5'>")
                    f.writelines(f"<h1>{council.name}</h1>\n")
                else:
                    f.writelines("<section class='mb-5 text-danger'>")
                    f.writelines(f"<h1>{council.name} (no twins)</h1>\n")

                f.writelines(
                    "<input class='form-control mt-3' value='What inspiration could you take from your council’s climate twin?'>\n"
                )

                if "twin" in context:
                    f.writelines(
                        f"<textarea class='form-control mt-3 font-monospace' rows='10'>{escaped_email_text}</textarea>\n"
                    )
                else:
                    f.writelines(
                        "<div class='alert alert-danger'>No twin for this council</div>"
                    )

                f.writelines("</section>\n")

            f.writelines(file_footer)

        print(f"output written to {html_filepath}")
