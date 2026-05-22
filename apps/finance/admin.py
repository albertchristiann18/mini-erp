from django.contrib import admin

from apps.finance.models import AccountsPayable, AccountsReceivable, PaymentRecord

admin.site.register(AccountsPayable)
admin.site.register(PaymentRecord)
admin.site.register(AccountsReceivable)
