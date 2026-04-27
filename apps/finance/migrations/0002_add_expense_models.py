from django.db import migrations, models
import core.utils
import django.db.models.deletion
import django_ulid.models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
        ('finance', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ExpenseCategory',
            fields=[
                ('cdate', models.DateTimeField(auto_now_add=True)),
                ('udate', models.DateTimeField(auto_now=True)),
                ('id', django_ulid.models.ULIDField(db_column='expense_category_id', default=core.utils.generate_ulid, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True, default='')),
                ('is_active', models.BooleanField(default=True)),
                ('company', models.ForeignKey(db_column='company_id', on_delete=django.db.models.deletion.CASCADE, to='core.company')),
            ],
            options={
                'db_table': 'expenses_expensecategory',
                'unique_together': {('company', 'name')},
            },
        ),
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('cdate', models.DateTimeField(auto_now_add=True)),
                ('udate', models.DateTimeField(auto_now=True)),
                ('id', django_ulid.models.ULIDField(db_column='expense_id', default=core.utils.generate_ulid, editable=False, primary_key=True, serialize=False)),
                ('expense_number', models.CharField(default='', editable=False, max_length=100, unique=True)),
                ('description', models.TextField()),
                ('amount', models.BigIntegerField()),
                ('expense_date', models.DateField()),
                ('payment_method', models.CharField(choices=[('CASH', 'Cash'), ('TRANSFER', 'Bank Transfer'), ('EWALLET', 'E-Wallet'), ('CREDIT', 'Credit Card')], default='TRANSFER', max_length=20)),
                ('receipt_file', models.FileField(blank=True, null=True, upload_to='expenses/receipts/')),
                ('is_recurring', models.BooleanField(default=False)),
                ('note', models.TextField(blank=True, default='')),
                ('company', models.ForeignKey(db_column='company_id', on_delete=django.db.models.deletion.CASCADE, to='core.company')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='expenses', to='finance.expensecategory')),
            ],
            options={
                'db_table': 'expenses_expense',
                'ordering': ['-expense_date'],
                'indexes': [models.Index(fields=['expense_date'], name='expenses_ex_expense_cf8a73_idx'), models.Index(fields=['category'], name='expenses_ex_categor_20264a_idx')],
            },
        ),
        # Create sequence for expense number generation
        migrations.RunSQL(
            sql="CREATE SEQUENCE IF NOT EXISTS expense_number_seq START WITH 1;",
            reverse_sql="DROP SEQUENCE IF EXISTS expense_number_seq;"
        ),
        # Trigger for Expense (Expense Number)
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION generate_expense_number()
            RETURNS TRIGGER AS $$
            DECLARE
                current_year TEXT;
                seq_val INT;
                exp_number TEXT;
            BEGIN
                current_year := TO_CHAR(NOW(), 'YYYY');
                seq_val := nextval('expense_number_seq');
                
                -- Build Expense Number: EXP-YYYY-SEQUENCE (padded to 4 digits)
                exp_number := 'EXP-' || current_year || '-' || LPAD(seq_val::text, 4, '0');
                
                NEW.expense_number := exp_number;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS trg_generate_expense_number ON expenses_expense;
            CREATE TRIGGER trg_generate_expense_number
            BEFORE INSERT ON expenses_expense
            FOR EACH ROW
            EXECUTE FUNCTION generate_expense_number();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS trg_generate_expense_number ON expenses_expense;
            DROP FUNCTION IF EXISTS generate_expense_number();
            """
        ),
    ]
