from django.db.models import F
import django_filters as filters


class NullsAlwaysLastOrderingFilter(filters.OrderingFilter):
    def filter(self, qs, value):
        ordering = [self.get_ordering_value(param) for param in value]

        if ordering:
            f_ordering = []
            for o in ordering:
                if not o:
                    continue
                if o[0] == "-":
                    f_ordering.append(F(o[1:]).desc(nulls_last=True))
                else:
                    f_ordering.append(F(o).asc(nulls_last=True))

            return qs.order_by(*f_ordering)

        return qs


class DefaultSecondarySortFilter(NullsAlwaysLastOrderingFilter):
    def __init__(self, *args, **kwargs):
        secondary = kwargs.pop("secondary", "")
        self.secondary = secondary
        self.rsecondary = "-" + secondary

        super().__init__(*args, **kwargs)

    def filter(self, qs, value):
        qs = super().filter(qs, value)
        if self.secondary == "":
            return qs

        if self.secondary not in value and self.rsecondary not in value:
            qs.order_by(self.secondary)

        return qs
