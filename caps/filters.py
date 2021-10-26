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
                if o[0] == '-':
                    f_ordering.append(F(o[1:]).desc(nulls_last=True))
                else:
                    f_ordering.append(F(o).asc(nulls_last=True))

            return qs.order_by(*f_ordering)

        return qs
