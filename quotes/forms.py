from django import forms
from .models import QuoteAcceptance


class QuoteAcceptanceForm(forms.ModelForm):
    notes = forms.CharField(
        required=False,
        label="Delivery notes",
        widget=forms.Textarea(
            attrs={
                "placeholder": "If your address works best with a specific courier (DPD, DHL, Parcelforce, etc.), you can tell us here. We’ll accommodate where possible at no extra cost.",
                "rows": 4,
            }
        ),
    )
    class Meta:
        model = QuoteAcceptance
        fields = [
            "full_name",
            "email",
            "phone",
            "company",
            "address_line1",
            "address_line2",
            "city",
            "postcode",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_classes = "w-full px-3 py-2 border border-slate-300 rounded-md text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        for name, field in self.fields.items():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {base_classes}".strip()
            if field.widget.__class__.__name__ == "Textarea":
                field.widget.attrs.setdefault("class", field.widget.attrs["class"] + " resize-y min-h-[120px]")