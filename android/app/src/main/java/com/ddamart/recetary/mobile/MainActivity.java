package com.ddamart.recetary.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.text.TextUtils;
import android.text.method.LinkMovementMethod;
import android.text.util.Linkify;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.Locale;

public class MainActivity extends Activity {
    private static final int PICK_DATABASE = 10;
    private static final int BG = Color.rgb(16, 19, 21);
    private static final int CARD = Color.rgb(28, 33, 36);
    private static final int BORDER = Color.rgb(54, 62, 66);
    private static final int TEXT = Color.rgb(239, 242, 241);
    private static final int MUTED = Color.rgb(157, 166, 165);
    private static final int ACCENT = Color.rgb(0, 128, 91);

    private SQLiteDatabase database;
    private EditText search;
    private TextView status;
    private RecipeAdapter adapter;
    private final ArrayList<RecipeRow> recipes = new ArrayList<>();

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        buildScreen();
        openStoredDatabase();
    }

    private void buildScreen() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);
        root.setPadding(dp(20), dp(22), dp(20), dp(12));

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        TextView title = text("◉  Recetary", 25, TEXT);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        header.addView(title, new LinearLayout.LayoutParams(0, dp(52), 1));

        Button importButton = button("Importar");
        importButton.setOnClickListener(v -> chooseDatabase());
        header.addView(importButton, new LinearLayout.LayoutParams(dp(112), dp(48)));
        root.addView(header);

        TextView heading = text("Tu biblioteca", 14, MUTED);
        heading.setPadding(dp(2), dp(18), 0, dp(8));
        root.addView(heading);

        search = new EditText(this);
        search.setHint("Buscar receta, ingrediente o URL…");
        search.setHintTextColor(Color.rgb(112, 122, 121));
        search.setTextColor(TEXT);
        search.setTextSize(16);
        search.setSingleLine(true);
        search.setInputType(InputType.TYPE_CLASS_TEXT);
        search.setPadding(dp(16), 0, dp(16), 0);
        search.setBackground(roundRect(CARD, BORDER, 14));
        search.addTextChangedListener(new SimpleTextWatcher() {
            @Override
            public void afterTextChanged(android.text.Editable value) {
                loadRecipes(value.toString());
            }
        });
        root.addView(search, new LinearLayout.LayoutParams(-1, dp(54)));

        status = text("Importa una base de datos para empezar.", 14, MUTED);
        status.setPadding(dp(2), dp(14), dp(2), dp(10));
        root.addView(status);

        ListView list = new ListView(this);
        list.setBackgroundColor(BG);
        list.setDivider(new android.graphics.drawable.ColorDrawable(Color.TRANSPARENT));
        list.setDividerHeight(dp(10));
        adapter = new RecipeAdapter();
        list.setAdapter(adapter);
        list.setOnItemClickListener(
                (parent, view, position, id) -> showRecipe(recipes.get(position).id));
        root.addView(list, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private TextView text(String value, int size, int color) {
        TextView view = new TextView(this);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        return view;
    }

    private Button button(String label) {
        Button button = new Button(this);
        button.setText(label);
        button.setTextColor(Color.WHITE);
        button.setTextSize(14);
        button.setAllCaps(false);
        button.setPadding(dp(8), 0, dp(8), 0);
        button.setBackground(roundRect(ACCENT, ACCENT, 12));
        return button;
    }

    private GradientDrawable roundRect(int fill, int stroke, int radius) {
        GradientDrawable drawable = new GradientDrawable();
        drawable.setColor(fill);
        drawable.setCornerRadius(dp(radius));
        drawable.setStroke(dp(1), stroke);
        return drawable;
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
            if (database != null) {
                database.close();
                database = null;
            }
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
            status.setText("Pulsa Importar para cargar tu biblioteca.");
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
                        cursor.isNull(2) ? "" : cursor.getString(2),
                        cursor.isNull(3) ? "" : cursor.getString(3)));
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
            LinearLayout content = new LinearLayout(this);
            content.setOrientation(LinearLayout.VERTICAL);
            content.setPadding(dp(20), dp(4), dp(20), dp(12));

            TextView subtitle = text(
                    recipe.isNull(1) ? "" : recipe.getString(1), 16, MUTED);
            if (!TextUtils.isEmpty(subtitle.getText())) {
                content.addView(subtitle, new LinearLayout.LayoutParams(-1, -2));
            }

            if (!recipe.isNull(2) && !TextUtils.isEmpty(recipe.getString(2))) {
                TextView description = text(recipe.getString(2), 15, TEXT);
                description.setPadding(0, dp(14), 0, dp(14));
                content.addView(description);
            }

            TextView meta = text(
                    metadata(recipe.getInt(4), recipe.isNull(5) ? null : recipe.getInt(5)),
                    13, MUTED);
            content.addView(meta);

            TextView ingredientsTitle = sectionTitle("INGREDIENTES");
            content.addView(ingredientsTitle);
            content.addView(text(ingredients(id), 15, TEXT));

            TextView stepsTitle = sectionTitle("PREPARACIÓN");
            content.addView(stepsTitle);
            content.addView(text(steps(id), 15, TEXT));

            if (!recipe.isNull(3) && recipe.getString(3).matches("(?i)^https?://.*")) {
                TextView source = text("\n" + recipe.getString(3), 13, Color.rgb(87, 202, 166));
                Linkify.addLinks(source, Linkify.WEB_URLS);
                source.setMovementMethod(LinkMovementMethod.getInstance());
                content.addView(source);
            }

            ScrollView scroll = new ScrollView(this);
            scroll.addView(content);
            new AlertDialog.Builder(this)
                    .setTitle(recipe.getString(0))
                    .setView(scroll)
                    .setPositiveButton("Cerrar", null)
                    .show();
        }
    }

    private TextView sectionTitle(String value) {
        TextView view = text("\n" + value, 12, Color.rgb(87, 202, 166));
        view.setTypeface(null, android.graphics.Typeface.BOLD);
        return view;
    }

    private String metadata(int servings, Integer minutes) {
        StringBuilder result = new StringBuilder();
        if (minutes != null) result.append(minutes).append(" min");
        if (servings > 0) {
            if (result.length() > 0) result.append("   ·   ");
            result.append(servings).append(" raciones");
        }
        return result.toString();
    }

    private String ingredients(String recipeId) {
        StringBuilder result = new StringBuilder();
        try (Cursor cursor = database.rawQuery(
                "SELECT i.name, ri.quantity_raw FROM recipe_ingredients ri " +
                        "JOIN ingredients i ON i.id = ri.ingredient_id " +
                        "WHERE ri.recipe_id = ? ORDER BY ri.is_pantry, i.name",
                new String[]{recipeId})) {
            while (cursor.moveToNext()) {
                result.append("• ").append(cursor.getString(0));
                if (!cursor.isNull(1)) result.append("  ").append(cursor.getString(1));
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
                if (!cursor.isNull(1)) result.append(cursor.getString(1)).append("\n");
                result.append(cursor.getString(2)).append("\n\n");
            }
        }
        return result.toString();
    }

    private class RecipeAdapter extends BaseAdapter {
        @Override public int getCount() { return recipes.size(); }
        @Override public RecipeRow getItem(int position) { return recipes.get(position); }
        @Override public long getItemId(int position) { return position; }

        @Override
        public View getView(int position, View convertView, ViewGroup parent) {
            RecipeRow row = getItem(position);
            LinearLayout card = new LinearLayout(MainActivity.this);
            card.setOrientation(LinearLayout.VERTICAL);
            card.setPadding(dp(18), dp(16), dp(18), dp(16));
            card.setBackground(roundRect(CARD, BORDER, 16));

            TextView title = text(row.title, 18, TEXT);
            title.setTypeface(null, android.graphics.Typeface.BOLD);
            title.setMaxLines(2);
            card.addView(title);

            if (!TextUtils.isEmpty(row.subtitle)) {
                TextView subtitle = text(row.subtitle, 14, MUTED);
                subtitle.setPadding(0, dp(6), 0, 0);
                subtitle.setMaxLines(2);
                card.addView(subtitle);
            }

            if (!TextUtils.isEmpty(row.source)) {
                TextView source = text(sourceLabel(row.source), 12, Color.rgb(87, 202, 166));
                source.setPadding(0, dp(10), 0, 0);
                card.addView(source);
            }
            return card;
        }
    }

    private String sourceLabel(String source) {
        if (source.contains("instagram")) return "INSTAGRAM";
        if (source.contains("youtube") || source.contains("youtu.be")) return "YOUTUBE";
        if (source.contains("twitter") || source.contains("x.com")) return "X / TWITTER";
        return "FUENTE";
    }

    private static class RecipeRow {
        final String id;
        final String title;
        final String subtitle;
        final String source;

        RecipeRow(String id, String title, String subtitle, String source) {
            this.id = id;
            this.title = title;
            this.subtitle = subtitle;
            this.source = source;
        }
    }

    private abstract static class SimpleTextWatcher implements android.text.TextWatcher {
        @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
        @Override public void onTextChanged(CharSequence s, int start, int before, int count) {}
    }
}
