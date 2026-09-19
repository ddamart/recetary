package com.ddamart.recetary.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.text.TextUtils;
import android.text.method.LinkMovementMethod;
import android.text.util.Linkify;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final int PICK_DATABASE = 10;

    private SQLiteDatabase database;
    private EditText search;
    private TextView status;
    private ArrayAdapter<RecipeRow> adapter;
    private final ArrayList<RecipeRow> recipes = new ArrayList<>();

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        buildScreen();
        openStoredDatabase();
    }

    private void buildScreen() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(24, 24, 24, 16);

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        TextView title = text("Recetary", 24, Color.rgb(30, 30, 30));
        header.addView(title, new LinearLayout.LayoutParams(0, -2, 1));
        Button importButton = new Button(this);
        importButton.setText("Importar");
        importButton.setOnClickListener(v -> chooseDatabase());
        header.addView(importButton);
        root.addView(header);

        search = new EditText(this);
        search.setHint("Buscar por título o URL");
        search.setSingleLine(true);
        search.setInputType(InputType.TYPE_CLASS_TEXT);
        search.setPadding(16, 8, 16, 8);
        search.addTextChangedListener(new SimpleTextWatcher() {
            @Override
            public void afterTextChanged(android.text.Editable value) {
                loadRecipes(value.toString());
            }
        });
        root.addView(search, new LinearLayout.LayoutParams(-1, 56));

        status = text("Importa una base de datos de Recetary para empezar.", 14, Color.GRAY);
        status.setPadding(0, 12, 0, 12);
        root.addView(status);

        ListView list = new ListView(this);
        adapter = new ArrayAdapter<RecipeRow>(this, android.R.layout.simple_list_item_2, android.R.id.text1, recipes) {
            @Override
            public View getView(int position, View convertView, ViewGroup parent) {
                View view = super.getView(position, convertView, parent);
                TextView first = view.findViewById(android.R.id.text1);
                TextView second = view.findViewById(android.R.id.text2);
                RecipeRow row = getItem(position);
                first.setText(row.title);
                second.setText(row.subtitle);
                return view;
            }
        };
        list.setAdapter(adapter);
        list.setOnItemClickListener((parent, view, position, id) -> showRecipe(recipes.get(position).id));
        root.addView(list, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
    }

    private TextView text(String value, int size, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        return view;
    }

    private void chooseDatabase() {
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.setType("*/*");
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        startActivityForResult(intent, PICK_DATABASE);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != PICK_DATABASE || resultCode != RESULT_OK || data == null) return;
        try {
            copyDatabase(data.getData());
            openStoredDatabase();
            Toast.makeText(this, "Base de datos importada", Toast.LENGTH_SHORT).show();
        } catch (Exception error) {
            Toast.makeText(this, "No se pudo importar la base de datos", Toast.LENGTH_LONG).show();
        }
    }

    private void copyDatabase(Uri source) throws Exception {
        File target = new File(getFilesDir(), "recetary.db");
        try (InputStream input = getContentResolver().openInputStream(source);
             FileOutputStream output = new FileOutputStream(target)) {
            if (input == null) throw new IllegalStateException("Empty database file");
            byte[] buffer = new byte[8192];
            int read;
            while ((read = input.read(buffer)) != -1) output.write(buffer, 0, read);
        }
    }

    private void openStoredDatabase() {
        File file = new File(getFilesDir(), "recetary.db");
        if (!file.exists()) {
            status.setText("Importa recetary.db desde el selector de archivos.");
            return;
        }
        try {
            if (database != null) database.close();
            database = SQLiteDatabase.openDatabase(
                    file.getPath(), null, SQLiteDatabase.OPEN_READONLY);
            loadRecipes("");
        } catch (Exception error) {
            status.setText("El archivo no parece una base de datos de Recetary.");
        }
    }

    private void loadRecipes(String query) {
        if (database == null || adapter == null) return;
        recipes.clear();
        String term = "%" + query.trim().toLowerCase(Locale.ROOT) + "%";
        try (Cursor cursor = database.rawQuery(
                "SELECT id, title, subtitle, source_ref FROM recipes " +
                        "WHERE LOWER(title) LIKE ? OR LOWER(COALESCE(subtitle, '')) LIKE ? " +
                        "OR LOWER(COALESCE(source_ref, '')) LIKE ? " +
                        "ORDER BY created_at DESC",
                new String[]{term, term, term})) {
            while (cursor.moveToNext()) {
                recipes.add(new RecipeRow(
                        cursor.getString(0),
                        cursor.getString(1),
                        cursor.isNull(2) ? "" : cursor.getString(2)));
            }
        } catch (Exception error) {
            status.setText("No se pudo leer la tabla de recetas.");
        }
        adapter.notifyDataSetChanged();
        status.setText(recipes.size() + (recipes.size() == 1 ? " receta" : " recetas"));
    }

    private void showRecipe(String id) {
        try (Cursor recipe = database.rawQuery(
                "SELECT title, subtitle, description, source_ref, servings, total_time_min " +
                        "FROM recipes WHERE id = ?", new String[]{id})) {
            if (!recipe.moveToFirst()) return;
            StringBuilder details = new StringBuilder(recipe.getString(0));
            if (!recipe.isNull(1) && !TextUtils.isEmpty(recipe.getString(1))) {
                details.append("\n\n").append(recipe.getString(1));
            }
            if (!recipe.isNull(2)) details.append("\n\n").append(recipe.getString(2));
            details.append("\n\nIngredientes:\n").append(ingredients(id));
            details.append("\nPreparación:\n").append(steps(id));
            if (!recipe.isNull(3) && recipe.getString(3).matches("(?i)^https?://.*")) {
                details.append("\n\n").append(recipe.getString(3));
            }

            TextView body = text(details.toString(), 16, Color.DKGRAY);
            body.setPadding(8, 8, 8, 8);
            Linkify.addLinks(body, Linkify.WEB_URLS);
            body.setMovementMethod(LinkMovementMethod.getInstance());
            android.widget.ScrollView scroll = new android.widget.ScrollView(this);
            scroll.addView(body);
            new AlertDialog.Builder(this)
                    .setTitle(recipe.getString(0))
                    .setView(scroll)
                    .setPositiveButton("Cerrar", null)
                    .show();
        }
    }

    private String ingredients(String recipeId) {
        StringBuilder result = new StringBuilder();
        try (Cursor cursor = database.rawQuery(
                "SELECT i.name, ri.quantity_raw FROM recipe_ingredients ri " +
                        "JOIN ingredients i ON i.id = ri.ingredient_id " +
                        "WHERE ri.recipe_id = ? ORDER BY ri.is_pantry, i.name",
                new String[]{recipeId})) {
            while (cursor.moveToNext()) {
                result.append("· ").append(cursor.getString(0));
                if (!cursor.isNull(1)) result.append(" — ").append(cursor.getString(1));
                result.append("\n");
            }
        }
        return result.toString();
    }

    private String steps(String recipeId) {
        StringBuilder result = new StringBuilder();
        try (Cursor cursor = database.rawQuery(
                "SELECT step_number, title, text FROM steps " +
                        "WHERE recipe_id = ? ORDER BY step_number",
                new String[]{recipeId})) {
            while (cursor.moveToNext()) {
                result.append(cursor.getInt(0)).append(". ");
                if (!cursor.isNull(1)) result.append(cursor.getString(1)).append(": ");
                result.append(cursor.getString(2)).append("\n\n");
            }
        }
        return result.toString();
    }

    private static class RecipeRow {
        final String id;
        final String title;
        final String subtitle;

        RecipeRow(String id, String title, String subtitle) {
            this.id = id;
            this.title = title;
            this.subtitle = subtitle;
        }

        @Override
        public String toString() {
            return title;
        }
    }

    private abstract static class SimpleTextWatcher implements android.text.TextWatcher {
        @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
        @Override public void onTextChanged(CharSequence s, int start, int before, int count) {}
    }
}
