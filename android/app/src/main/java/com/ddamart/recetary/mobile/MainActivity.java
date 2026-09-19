package com.ddamart.recetary.mobile;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.graphics.Color;
import android.graphics.BitmapFactory;
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
import android.view.WindowInsets;
import android.widget.BaseAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
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
import java.util.Random;

public class MainActivity extends Activity {
    private static final int PICK_LIBRARY = 10;
    private static final int PAGE_SIZE = 50;
    private static final int BG = Color.rgb(16, 19, 21);
    private static final int CARD = Color.rgb(28, 33, 36);
    private static final int BORDER = Color.rgb(54, 62, 66);
    private static final int TEXT = Color.rgb(239, 242, 241);
    private static final int MUTED = Color.rgb(157, 166, 165);
    private static final int ACCENT = Color.rgb(0, 128, 91);

    private SQLiteDatabase database;
    private EditText search;
    private TextView status;
    private Button loadMore;
    private RecipeAdapter adapter;
    private final ArrayList<RecipeRow> recipes = new ArrayList<>();
    private String currentQuery = "";
    private boolean hasMore;
    private boolean detailOpen;

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
        applySystemInsets(root, 8);

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        TextView title = text("◉  Recetary", 25, TEXT);
        title.setTypeface(null, android.graphics.Typeface.BOLD);
        header.addView(title, new LinearLayout.LayoutParams(-1, dp(48)));
        root.addView(header);

        LinearLayout actions = new LinearLayout(this);
        actions.setGravity(Gravity.CENTER_VERTICAL);
        Button importButton = button("Importar biblioteca");
        importButton.setOnClickListener(v -> chooseDatabase());
        actions.addView(importButton, new LinearLayout.LayoutParams(0, dp(44), 2));

        Button randomButton = button("Aleatoria");
        randomButton.setOnClickListener(v -> showRandomRecipe());
        LinearLayout.LayoutParams actionParams = new LinearLayout.LayoutParams(0, dp(44), 1);
        actionParams.setMargins(dp(8), 0, 0, 0);
        actions.addView(randomButton, actionParams);
        root.addView(actions);

        TextView heading = text("Tu biblioteca", 14, MUTED);
        heading.setPadding(dp(2), dp(14), 0, dp(8));
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
        loadMore = button("Cargar más");
        loadMore.setOnClickListener(v -> loadMoreRecipes());
        list.addFooterView(loadMore, null, false);
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
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);
        startActivityForResult(intent, PICK_LIBRARY);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null || data.getData() == null) return;
        try {
            if (requestCode != PICK_LIBRARY) return;
            if (database != null) {
                database.close();
                database = null;
            }
            importLibrary(data.getData());
            openStoredDatabase();
            Toast.makeText(this, "Biblioteca importada", Toast.LENGTH_SHORT).show();
        } catch (Exception error) {
            Toast.makeText(this, "No se pudo importar la biblioteca", Toast.LENGTH_LONG).show();
        }
    }

    private void importLibrary(Uri tree) throws Exception {
        File imageDirectory = new File(getFilesDir(), "images");
        if (!imageDirectory.exists() && !imageDirectory.mkdirs()) {
            throw new IllegalStateException("Could not create image directory");
        }
        File databaseFile = new File(getFilesDir(), "recetary.db");
        if (databaseFile.exists() && !databaseFile.delete()) {
            throw new IllegalStateException("Could not replace database");
        }
        importLibraryFromTree(tree, imageDirectory, databaseFile);
        if (!databaseFile.isFile()) {
            throw new IllegalStateException("The selected folder has no recetary.db");
        }
    }

    private void importLibraryFromTree(Uri tree, File imageDirectory, File databaseFile) throws Exception {
        Uri children = android.provider.DocumentsContract.buildChildDocumentsUriUsingTree(
                tree, android.provider.DocumentsContract.getTreeDocumentId(tree));
        try (Cursor cursor = getContentResolver().query(
                children, new String[]{
                        android.provider.DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                        android.provider.DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                        android.provider.DocumentsContract.Document.COLUMN_MIME_TYPE
                }, null, null, null)) {
            if (cursor == null) return;
            while (cursor.moveToNext()) {
                String id = cursor.getString(0);
                String name = cursor.getString(1);
                String mime = cursor.getString(2);
                Uri document = android.provider.DocumentsContract.buildDocumentUriUsingTree(tree, id);
                if (android.provider.DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {
                    importLibraryFromTree(document, imageDirectory, databaseFile);
                } else if ("recetary.db".equalsIgnoreCase(name)) {
                    copyFile(document, databaseFile);
                } else if (mime != null && mime.startsWith("image/")) {
                    copyFile(document, new File(imageDirectory, name));
                }
            }
        }
    }

    private void copyFile(Uri source, File target) throws Exception {
        try (InputStream input = getContentResolver().openInputStream(source);
             FileOutputStream output = new FileOutputStream(target)) {
            if (input == null) throw new IllegalStateException("Empty image file");
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
        currentQuery = query.trim();
        recipes.clear();
        loadPage(false);
    }

    private void loadMoreRecipes() {
        if (database == null || !hasMore) return;
        loadPage(true);
    }

    private void loadPage(boolean append) {
        String term = "%" + currentQuery.toLowerCase(Locale.ROOT) + "%";
        int offset = append ? recipes.size() : 0;
        try (Cursor cursor = database.rawQuery(
                "SELECT id, title, subtitle, source_ref, image_path FROM recipes " +
                        "WHERE LOWER(title) LIKE ? OR LOWER(COALESCE(subtitle, '')) LIKE ? " +
                        "OR LOWER(COALESCE(source_ref, '')) LIKE ? " +
                        "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                new String[]{term, term, term, String.valueOf(PAGE_SIZE), String.valueOf(offset)})) {
            while (cursor.moveToNext()) {
                recipes.add(new RecipeRow(
                        cursor.getString(0),
                        cursor.getString(1),
                        cursor.isNull(2) ? "" : cursor.getString(2),
                        cursor.isNull(3) ? "" : cursor.getString(3),
                        cursor.isNull(4) ? "" : cursor.getString(4)));
            }
            hasMore = cursor.getCount() == PAGE_SIZE;
        } catch (Exception error) {
            status.setText("No se pudo leer la tabla de recetas.");
            hasMore = false;
        }
        adapter.notifyDataSetChanged();
        status.setText(recipes.size() + (recipes.size() == 1 ? " receta" : " recetas"));
        loadMore.setVisibility(hasMore ? View.VISIBLE : View.GONE);
    }

    private void showRandomRecipe() {
        if (database == null) {
            Toast.makeText(this, "Importa una base de datos para empezar", Toast.LENGTH_SHORT).show();
            return;
        }
        String term = "%" + currentQuery.toLowerCase(Locale.ROOT) + "%";
        try (Cursor cursor = database.rawQuery(
                "SELECT id FROM recipes " +
                        "WHERE LOWER(title) LIKE ? OR LOWER(COALESCE(subtitle, '')) LIKE ? " +
                        "OR LOWER(COALESCE(source_ref, '')) LIKE ? " +
                        "ORDER BY RANDOM() LIMIT 1",
                new String[]{term, term, term})) {
            if (cursor.moveToFirst()) {
                showRecipe(cursor.getString(0));
                return;
            }
        }
        if (recipes.isEmpty()) {
            Toast.makeText(this, "No hay recetas para elegir", Toast.LENGTH_SHORT).show();
            return;
        }
        showRecipe(recipes.get(new Random().nextInt(recipes.size())).id);
    }

    private void showRecipe(String id) {
        try (Cursor recipe = database.rawQuery(
                "SELECT title, subtitle, description, source_ref, servings, total_time_min, image_path " +
                        "FROM recipes WHERE id = ?", new String[]{id})) {
            if (!recipe.moveToFirst()) return;
            detailOpen = true;
            LinearLayout page = new LinearLayout(this);
            page.setOrientation(LinearLayout.VERTICAL);
            page.setBackgroundColor(BG);
            applySystemInsets(page, 8);

            LinearLayout toolbar = new LinearLayout(this);
            toolbar.setGravity(Gravity.CENTER_VERTICAL);
            Button back = button("‹  Volver");
            back.setOnClickListener(v -> showMainPage());
            toolbar.addView(back, new LinearLayout.LayoutParams(dp(120), dp(44)));
            TextView pageTitle = text("Receta", 20, TEXT);
            pageTitle.setTypeface(null, android.graphics.Typeface.BOLD);
            pageTitle.setGravity(Gravity.CENTER);
            toolbar.addView(pageTitle, new LinearLayout.LayoutParams(0, dp(44), 1));
            page.addView(toolbar);

            ScrollView scroll = new ScrollView(this);
            LinearLayout content = new LinearLayout(this);
            content.setOrientation(LinearLayout.VERTICAL);
            content.setPadding(dp(20), dp(4), dp(20), dp(12));

            if (!recipe.isNull(6)) {
                ImageView image = recipeImage(recipe.getString(6), -1, 180);
                if (image != null) content.addView(image);
            }

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

            scroll.addView(content);
            page.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));
            setContentView(page);
        }
    }

    private void showMainPage() {
        detailOpen = false;
        buildScreen();
        loadRecipes(currentQuery);
    }

    @Override
    public void onBackPressed() {
        if (detailOpen) {
            showMainPage();
        } else {
            super.onBackPressed();
        }
    }

    private TextView sectionTitle(String value) {
        TextView view = text("\n" + value, 12, Color.rgb(87, 202, 166));
        view.setTypeface(null, android.graphics.Typeface.BOLD);
        return view;
    }

    private void applySystemInsets(View view, int topPadding) {
        view.setPadding(dp(20), dp(topPadding), dp(20), dp(12));
        view.setOnApplyWindowInsetsListener((target, insets) -> {
            int top = 0;
            int bottom = 0;
            if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.R) {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                top = bars.top;
                bottom = bars.bottom;
            } else {
                top = insets.getSystemWindowInsetTop();
                bottom = insets.getSystemWindowInsetBottom();
            }
            target.setPadding(dp(20), top + dp(topPadding), dp(20), bottom + dp(20));
            return insets;
        });
        view.requestApplyInsets();
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

            LinearLayout body = new LinearLayout(MainActivity.this);
            body.setGravity(Gravity.CENTER_VERTICAL);
            ImageView image = recipeImage(row.imagePath, 78, 78);
            if (image != null) {
                body.addView(image);
            }
            LinearLayout details = new LinearLayout(MainActivity.this);
            details.setOrientation(LinearLayout.VERTICAL);
            if (image != null) {
                LinearLayout.LayoutParams detailsParams = new LinearLayout.LayoutParams(0, -2, 1);
                detailsParams.setMargins(dp(14), 0, 0, 0);
                body.addView(details, detailsParams);
            } else {
                body.addView(details, new LinearLayout.LayoutParams(-1, -2));
            }

            TextView title = text(row.title, 18, TEXT);
            title.setTypeface(null, android.graphics.Typeface.BOLD);
            title.setMaxLines(2);
            details.addView(title);

            if (!TextUtils.isEmpty(row.subtitle)) {
                TextView subtitle = text(row.subtitle, 14, MUTED);
                subtitle.setPadding(0, dp(6), 0, 0);
                subtitle.setMaxLines(2);
                details.addView(subtitle);
            }

            if (!TextUtils.isEmpty(row.source)) {
                TextView source = text(sourceLabel(row.source), 12, Color.rgb(87, 202, 166));
                source.setPadding(0, dp(10), 0, 0);
                details.addView(source);
            }
            card.addView(body);
            return card;
        }
    }

    private ImageView recipeImage(String imagePath, int width, int height) {
        if (TextUtils.isEmpty(imagePath)) return null;
        File file = new File(getFilesDir(), "images/" + imagePath);
        if (!file.isFile()) return null;
        ImageView image = new ImageView(this);
        image.setImageBitmap(BitmapFactory.decodeFile(file.getPath()));
        image.setScaleType(ImageView.ScaleType.CENTER_CROP);
        image.setBackground(roundRect(CARD, BORDER, 12));
        image.setClipToOutline(true);
        image.setLayoutParams(new LinearLayout.LayoutParams(
                width < 0 ? -1 : dp(width), dp(height)));
        return image;
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
        final String imagePath;

        RecipeRow(String id, String title, String subtitle, String source, String imagePath) {
            this.id = id;
            this.title = title;
            this.subtitle = subtitle;
            this.source = source;
            this.imagePath = imagePath;
        }
    }

    private abstract static class SimpleTextWatcher implements android.text.TextWatcher {
        @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
        @Override public void onTextChanged(CharSequence s, int start, int before, int count) {}
    }
}
