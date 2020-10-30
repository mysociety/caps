from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('caps', '0023_auto_20201030_1815'),
    ]

    migration = '''
        CREATE TRIGGER text_search_update BEFORE INSERT OR UPDATE
        ON caps_plandocument FOR EACH ROW EXECUTE FUNCTION
        tsvector_update_trigger(text_search, 'pg_catalog.english', text);

        -- Force triggers to run and populate the text_search column.
        UPDATE caps_plandocument set ID = ID;
    '''

    reverse_migration = '''
        DROP TRIGGER text_search ON caps_plandocument;
    '''

    operations = [
        migrations.RunSQL(migration, reverse_migration)
    ]
