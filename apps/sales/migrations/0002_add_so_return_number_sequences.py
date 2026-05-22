# Generated manually for SO and Return number sequences

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0001_initial'),
    ]

    operations = [
        # 1. Sequence for Sales Order number
        migrations.RunSQL(
            sql="CREATE SEQUENCE so_number_seq START WITH 1;",
            reverse_sql="DROP SEQUENCE so_number_seq;"
        ),

        # 2. Trigger for SalesOrder (SO Number)
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION generate_so_number()
            RETURNS TRIGGER AS $$
            DECLARE
                current_year TEXT;
                seq_val INT;
                so_number TEXT;
            BEGIN
                current_year := TO_CHAR(NOW(), 'YYYY');
                seq_val := nextval('so_number_seq');

                -- Build SO Number: SO-YYYY-SEQUENCE (padded to 4 digits)
                so_number := 'SO-' || current_year || '-' || LPAD(seq_val::text, 4, '0');

                NEW.order_number := so_number;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER trg_generate_so_number
            BEFORE INSERT ON sales_salesorder
            FOR EACH ROW
            EXECUTE FUNCTION generate_so_number();
            """,
            reverse_sql="""
            DROP TRIGGER trg_generate_so_number ON sales_salesorder;
            DROP FUNCTION generate_so_number();
            """
        ),

        # 3. Sequence for Sales Return number
        migrations.RunSQL(
            sql="CREATE SEQUENCE ret_number_seq START WITH 1;",
            reverse_sql="DROP SEQUENCE ret_number_seq;"
        ),

        # 4. Trigger for SalesReturn (Return Number)
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION generate_ret_number()
            RETURNS TRIGGER AS $$
            DECLARE
                current_year TEXT;
                seq_val INT;
                ret_number TEXT;
            BEGIN
                current_year := TO_CHAR(NOW(), 'YYYY');
                seq_val := nextval('ret_number_seq');

                -- Build Return Number: RET-YYYY-SEQUENCE (padded to 4 digits)
                ret_number := 'RET-' || current_year || '-' || LPAD(seq_val::text, 4, '0');

                NEW.return_number := ret_number;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER trg_generate_ret_number
            BEFORE INSERT ON sales_salesreturn
            FOR EACH ROW
            EXECUTE FUNCTION generate_ret_number();
            """,
            reverse_sql="""
            DROP TRIGGER trg_generate_ret_number ON sales_salesreturn;
            DROP FUNCTION generate_ret_number();
            """
        ),
    ]
