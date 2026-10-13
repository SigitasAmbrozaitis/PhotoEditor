/**
 * Generated from openapi.json by scripts/gen-api.ts. Do not edit by hand.
 * Regenerate with: npm run gen:api
 */

export interface paths {
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/library": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Library */
        get: operations["library_api_library_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/library/folders": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Library Folders */
        get: operations["library_folders_api_library_folders_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/library/current": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Open Folder */
        put: operations["open_folder_api_library_current_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/library/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Import Folder */
        post: operations["import_folder_api_library_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/fs/dirs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Fs Dirs */
        get: operations["fs_dirs_api_fs_dirs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Photos */
        get: operations["list_photos_api_photos_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/{photo_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Photo Detail */
        get: operations["photo_detail_api_photos__photo_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/{photo_id}/sidecar": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Photo Sidecar
         * @description The camera's own JPEG of a RAW (if it saved one), for comparing with the default look.
         */
        get: operations["photo_sidecar_api_photos__photo_id__sidecar_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/{photo_id}/edit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Save Edit
         * @description Save a photo's adjustments (the full set; only what differs from the defaults is stored).
         */
        put: operations["save_edit_api_photos__photo_id__edit_put"];
        post?: never;
        /**
         * Reset Edit
         * @description Drop the photo's own tweaks (its style stays; PUT /style with null removes the style).
         */
        delete: operations["reset_edit_api_photos__photo_id__edit_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/{photo_id}/geometry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Change Geometry
         * @description Change the photo's crop, straighten angle, aspect lock, quarter turn or flips (only the fields given).
         *     Flips and turns carry the crop along; after an angle or aspect change the crop shrinks to fit the
         *     straightened photo. An explicit crop that reaches outside it is rejected.
         */
        post: operations["change_geometry_api_photos__photo_id__geometry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/{photo_id}/geometry/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Preview Geometry
         * @description The geometry a change would give, starting from ``geometry`` (e.g. the crop tool's draft). Nothing is
         *     saved; save it with PUT /edit.
         */
        post: operations["preview_geometry_api_photos__photo_id__geometry_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/{photo_id}/subject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Photo Subject
         * @description The photo's main subject: the box set by hand, else the detected one (detected now if needed, which
         *     takes a few seconds the first time).
         */
        get: operations["photo_subject_api_photos__photo_id__subject_get"];
        /**
         * Set Photo Subject
         * @description Set the subject by hand (upright photo coordinates), or ``{"box": null}`` to use the detected one.
         *     Changes no pixels: the edit's revision and its previews stay.
         */
        put: operations["set_photo_subject_api_photos__photo_id__subject_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/{photo_id}/suggest-crop": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Suggest Crop
         * @description A crop of the ratio framing the photo's subject, in the frame of the given (draft) geometry. Nothing
         *     is saved.
         */
        post: operations["suggest_crop_api_photos__photo_id__suggest_crop_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/{photo_id}/style": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Photo Style
         * @description Give the photo a style right away (null removes it). Tweaks of what the style sets are replaced.
         */
        put: operations["set_photo_style_api_photos__photo_id__style_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/engine": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Engine */
        get: operations["engine_api_engine_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/{photo_id}/thumbnail": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Photo Thumbnail */
        get: operations["photo_thumbnail_api_photos__photo_id__thumbnail_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/{photo_id}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Photo Preview */
        get: operations["photo_preview_api_photos__photo_id__preview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/{photo_id}/zoom/{level}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Photo Zoom
         * @description The zoom view at 50 or 100 %. Starts its decode if needed (100 %: ~13 to 25 s the first time); ask
         *     again until ``state`` is ``ready``.
         */
        get: operations["photo_zoom_api_photos__photo_id__zoom__level__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/photos/{photo_id}/zoom/{level}/tiles/{tx}/{ty}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Photo Tile */
        get: operations["photo_tile_api_photos__photo_id__zoom__level__tiles__tx___ty__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/styles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Styles */
        get: operations["list_styles_api_styles_get"];
        put?: never;
        /** Create Style */
        post: operations["create_style_api_styles_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/styles/{style_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Style */
        get: operations["style_api_styles__style_id__get"];
        /**
         * Update Style
         * @description Change a style (409 if it changed since ``expected_version``). Every photo using it follows.
         */
        put: operations["update_style_api_styles__style_id__put"];
        post?: never;
        /**
         * Delete Style
         * @description Delete a style; the photos using it drop back to no style and keep their own tweaks.
         */
        delete: operations["delete_style_api_styles__style_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/styles/from-photo": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Create Style From Photo
         * @description A new style from a photo's current look (chosen groups; exposure and white balance as rules).
         */
        post: operations["create_style_from_photo_api_styles_from_photo_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/styles/{style_id}/from-photo": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Update Style From Photo */
        post: operations["update_style_from_photo_api_styles__style_id__from_photo_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/styles/{style_id}/duplicate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Duplicate Style */
        post: operations["duplicate_style_api_styles__style_id__duplicate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/styles/{style_id}/history": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Style History
         * @description Saved versions, newest first.
         */
        get: operations["style_history_api_styles__style_id__history_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/styles/{style_id}/versions/{version}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Style Version */
        get: operations["style_version_api_styles__style_id__versions__version__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/styles/{style_id}/versions/{version}/photos/{photo_id}.jpg": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Style Version Render
         * @description A photo with one version of the style (none of its own tweaks), to compare versions side by side.
         */
        get: operations["style_version_render_api_styles__style_id__versions__version__photos__photo_id__jpg_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/styles/{style_id}/diff": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Style Diff */
        get: operations["style_diff_api_styles__style_id__diff_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/styles/{style_id}/revert": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Revert Style */
        post: operations["revert_style_api_styles__style_id__revert_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/styles/{style_id}/samples": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Render Style Samples
         * @description Render before/after sample pairs from library photos (a job).
         */
        post: operations["render_style_samples_api_styles__style_id__samples_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/styles/{style_id}/report": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Style Report
         * @description How consistent the style makes the photos (default: its test set, else the photos using it).
         */
        post: operations["style_report_api_styles__style_id__report_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/styles/{style_id}/samples/{name}/{which}.jpg": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Style Sample */
        get: operations["style_sample_api_styles__style_id__samples__name___which__jpg_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/export-presets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Presets */
        get: operations["list_presets_api_export_presets_get"];
        put?: never;
        /** Create Preset */
        post: operations["create_preset_api_export_presets_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/export-presets/{preset_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Preset */
        get: operations["preset_api_export_presets__preset_id__get"];
        /** Update Preset */
        put: operations["update_preset_api_export_presets__preset_id__put"];
        post?: never;
        /** Delete Preset */
        delete: operations["delete_preset_api_export_presets__preset_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/export-presets/{preset_id}/duplicate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Duplicate Preset */
        post: operations["duplicate_preset_api_export_presets__preset_id__duplicate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/export/plan": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Export Plan
         * @description What an export would write: names, sizes, collisions and warnings. Nothing is written.
         */
        post: operations["export_plan_api_export_plan_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/export/destinations": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Export Destinations
         * @description Recently used export folders, newest first.
         */
        get: operations["export_destinations_api_export_destinations_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/export/destination-check": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Destination Check */
        post: operations["destination_check_api_export_destination_check_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/export/reveal": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Reveal Export
         * @description Show an exported file in Explorer. Only files exported in this session can be shown.
         */
        post: operations["reveal_export_api_export_reveal_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/review-settings": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Review Settings */
        get: operations["review_settings_api_review_settings_get"];
        /**
         * Set Review Settings
         * @description Save the rules; open reviews are sorted again by them.
         */
        put: operations["set_review_settings_api_review_settings_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/reviews": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Reviews */
        get: operations["list_reviews_api_reviews_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/reviews/{review_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Get Review
         * @description The review, refreshed against the photos' current edits and subjects.
         */
        get: operations["get_review_api_reviews__review_id__get"];
        put?: never;
        post?: never;
        /** Discard Review */
        delete: operations["discard_review_api_reviews__review_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/reviews/{review_id}/items/{photo_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /**
         * Update Review Item
         * @description Set a photo's zoom (null = automatic; a zoom approves it) or approve it.
         */
        patch: operations["update_review_item_api_reviews__review_id__items__photo_id__patch"];
        trace?: never;
    };
    "/api/reviews/{review_id}/items/{photo_id}/subject": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Set Review Subject
         * @description Choose a candidate, draw a box, or go back to the detected subject; saved to the photo's edit, and
         *     the photo is approved.
         */
        put: operations["set_review_subject_api_reviews__review_id__items__photo_id__subject_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/reviews/{review_id}/items/{photo_id}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Review Preview
         * @description The photo framed as the export will frame it (800 px long edge).
         */
        get: operations["review_preview_api_reviews__review_id__items__photo_id__preview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/reviews/{review_id}/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Export Review
         * @description Export the approved photos (scope ``approved``) or all but the unusable ones (``all``).
         */
        post: operations["export_review_api_reviews__review_id__export_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/jobs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Jobs */
        get: operations["list_jobs_api_jobs_get"];
        put?: never;
        /**
         * Create Job
         * @description Apply a style, export, apply then export, detect subjects, or prepare an export for review (the job's
         *     ``review_id`` names the review).
         */
        post: operations["create_job_api_jobs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/jobs/{job_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Job */
        get: operations["job_api_jobs__job_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/jobs/{job_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel Job */
        post: operations["cancel_job_api_jobs__job_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /**
         * AdjustmentGroup
         * @enum {string}
         */
        AdjustmentGroup: "white_balance" | "tone" | "presence" | "tone_curve" | "hsl" | "color_grading" | "detail" | "effects" | "geometry" | "lens";
        /**
         * AdjustmentParams
         * @description Complete set of global adjustments. All defaults = identity (no change).
         */
        "AdjustmentParams-Input": {
            white_balance?: components["schemas"]["WhiteBalance-Input"];
            tone?: components["schemas"]["Tone-Input"];
            presence?: components["schemas"]["Presence-Input"];
            tone_curve?: components["schemas"]["ToneCurve-Input"];
            hsl?: components["schemas"]["Hsl-Input"];
            color_grading?: components["schemas"]["ColorGrading-Input"];
            detail?: components["schemas"]["Detail-Input"];
            effects?: components["schemas"]["Effects-Input"];
            geometry?: components["schemas"]["Geometry-Input"];
            lens?: components["schemas"]["Lens-Input"];
        };
        /**
         * AdjustmentParams
         * @description Complete set of global adjustments. All defaults = identity (no change).
         */
        "AdjustmentParams-Output": {
            white_balance: components["schemas"]["WhiteBalance-Output"];
            tone: components["schemas"]["Tone-Output"];
            presence: components["schemas"]["Presence-Output"];
            tone_curve: components["schemas"]["ToneCurve-Output"];
            hsl: components["schemas"]["Hsl-Output"];
            color_grading: components["schemas"]["ColorGrading-Output"];
            detail: components["schemas"]["Detail-Output"];
            effects: components["schemas"]["Effects-Output"];
            geometry: components["schemas"]["Geometry-Output"];
            lens: components["schemas"]["Lens-Output"];
        };
        /** ApplyAndExportRequest */
        ApplyAndExportRequest: {
            /** Photo Ids */
            photo_ids: string[];
            /**
             * Kind
             * @default apply_and_export
             * @constant
             */
            kind: "apply_and_export";
            /** Style Id */
            style_id: string;
            /**
             * Even Out
             * @default false
             */
            even_out: boolean;
            /** Preset Id */
            preset_id?: string | null;
            settings: components["schemas"]["ExportSettings-Input"];
            /** Destination */
            destination: string;
        };
        /** ApplyStyleRequest */
        ApplyStyleRequest: {
            /** Photo Ids */
            photo_ids: string[];
            /**
             * Kind
             * @default apply_style
             * @constant
             */
            kind: "apply_style";
            /**
             * Style Id
             * @description None removes the style from the photos.
             */
            style_id: string | null;
            /**
             * Even Out
             * @description Store the selection's median as each photo's group reference, so the style's exposure rule evens the photos out against each other.
             * @default false
             */
            even_out: boolean;
        };
        /**
         * AsShot
         * @description The white balance the camera recorded (what temperature/tint = None means).
         */
        AsShot: {
            /**
             * Temperature
             * @description Kelvin.
             */
            temperature: number;
            /**
             * Tint
             * @description Green (-) / magenta (+), Lightroom units.
             */
            tint: number;
        };
        /** AspectSettings */
        "AspectSettings-Input": {
            /**
             * Ratio
             * @description Crop to this aspect ratio, e.g. '4:5'. None = keep the photo's own aspect.
             */
            ratio?: string | null;
            /**
             * @description auto = follow the photo; otherwise force the ratio's orientation.
             * @default auto
             */
            orientation: components["schemas"]["Orientation"];
            /**
             * @description What the aspect crop frames: the photo's main subject (set by hand or detected; centered when there is none) or the center.
             * @default center
             */
            anchor: components["schemas"]["CropAnchor"];
            /**
             * @description auto = tighten the subject crop until the subject fills `subject_fill` of it, as far as a half-size decode still covers the output (fast). Needs a ratio and the 'subject' anchor. Photos with a crop of their own are never zoomed automatically.
             * @default off
             */
            zoom: components["schemas"]["AspectZoom"];
            /**
             * Subject Fill
             * @description Automatic zoom: the share of the crop's width or height the subject should fill.
             * @default 0.4
             */
            subject_fill: number;
        };
        /** AspectSettings */
        "AspectSettings-Output": {
            /**
             * Ratio
             * @description Crop to this aspect ratio, e.g. '4:5'. None = keep the photo's own aspect.
             */
            ratio: string | null;
            /**
             * @description auto = follow the photo; otherwise force the ratio's orientation.
             * @default auto
             */
            orientation: components["schemas"]["Orientation"];
            /**
             * @description What the aspect crop frames: the photo's main subject (set by hand or detected; centered when there is none) or the center.
             * @default center
             */
            anchor: components["schemas"]["CropAnchor"];
            /**
             * @description auto = tighten the subject crop until the subject fills `subject_fill` of it, as far as a half-size decode still covers the output (fast). Needs a ratio and the 'subject' anchor. Photos with a crop of their own are never zoomed automatically.
             * @default off
             */
            zoom: components["schemas"]["AspectZoom"];
            /**
             * Subject Fill
             * @description Automatic zoom: the share of the crop's width or height the subject should fill.
             * @default 0.4
             */
            subject_fill: number;
        };
        /**
         * AspectZoom
         * @enum {string}
         */
        AspectZoom: "off" | "auto";
        /**
         * CollisionPolicy
         * @enum {string}
         */
        CollisionPolicy: "suffix" | "overwrite" | "skip";
        /**
         * CollisionStatus
         * @enum {string}
         */
        CollisionStatus: "new" | "renamed" | "overwrite" | "skip";
        /** ColorGrading */
        "ColorGrading-Input": {
            shadows?: components["schemas"]["GradeWheel-Input"];
            midtones?: components["schemas"]["GradeWheel-Input"];
            highlights?: components["schemas"]["GradeWheel-Input"];
            global?: components["schemas"]["GradeWheel-Input"];
            /**
             * Blending
             * @description Overlap between the tonal ranges.
             * @default 50
             */
            blending: number;
            /**
             * Balance
             * @description Shift the shadows/highlights split point.
             * @default 0
             */
            balance: number;
        };
        /** ColorGrading */
        "ColorGrading-Output": {
            shadows: components["schemas"]["GradeWheel-Output"];
            midtones: components["schemas"]["GradeWheel-Output"];
            highlights: components["schemas"]["GradeWheel-Output"];
            global: components["schemas"]["GradeWheel-Output"];
            /**
             * Blending
             * @description Overlap between the tonal ranges.
             * @default 50
             */
            blending: number;
            /**
             * Balance
             * @description Shift the shadows/highlights split point.
             * @default 0
             */
            balance: number;
        };
        /**
         * ColorSpace
         * @enum {string}
         */
        ColorSpace: "srgb" | "display_p3" | "adobe_rgb";
        /** ConsistencyReport */
        ConsistencyReport: {
            /** Style Id */
            style_id: string | null;
            /** Look Hash */
            look_hash: string | null;
            /** Photos */
            photos: components["schemas"]["ReportPhoto"][];
            /** Spread */
            spread: components["schemas"]["Spread"][];
        };
        /**
         * CropAnchor
         * @enum {string}
         */
        CropAnchor: "subject" | "center";
        /**
         * CropPlacement
         * @enum {string}
         */
        CropPlacement: "centered" | "thirds";
        /**
         * CropRect
         * @description Crop rectangle in normalized coordinates (0..1) of the frame after flips and the quarter turn.
         *
         *     The straighten angle turns the image inside that frame, so the rectangle stays put while the angle
         *     changes. It must lie inside the straightened image (no blank corners); that needs the photo's size, so
         *     core checks it when an edit is saved.
         */
        "CropRect-Input": {
            /**
             * Left
             * @default 0
             */
            left: number;
            /**
             * Top
             * @default 0
             */
            top: number;
            /**
             * Right
             * @default 1
             */
            right: number;
            /**
             * Bottom
             * @default 1
             */
            bottom: number;
        };
        /**
         * CropRect
         * @description Crop rectangle in normalized coordinates (0..1) of the frame after flips and the quarter turn.
         *
         *     The straighten angle turns the image inside that frame, so the rectangle stays put while the angle
         *     changes. It must lie inside the straightened image (no blank corners); that needs the photo's size, so
         *     core checks it when an edit is saved.
         */
        "CropRect-Output": {
            /**
             * Left
             * @default 0
             */
            left: number;
            /**
             * Top
             * @default 0
             */
            top: number;
            /**
             * Right
             * @default 1
             */
            right: number;
            /**
             * Bottom
             * @default 1
             */
            bottom: number;
        };
        /** CropSuggestion */
        CropSuggestion: {
            /** @description The suggested crop, normalized to the frame of the given geometry. */
            crop: components["schemas"]["CropRect-Output"];
            /**
             * Aspect
             * @description The ratio used, turned to the chosen orientation (e.g. '5:4').
             */
            aspect: string;
            placement: components["schemas"]["CropPlacement"];
            /**
             * Zoom
             * @description The zoom actually used (capped where the subject plus margin fills it).
             */
            zoom: number;
            source: components["schemas"]["SubjectSource"];
            kind: components["schemas"]["SubjectKind"] | null;
            /** @description The subject used, normalized to the frame of the given geometry. */
            subject: components["schemas"]["SubjectBox"] | null;
            /** Warnings */
            warnings: string[];
        };
        /** CropSuggestionRequest */
        CropSuggestionRequest: {
            /** @description The geometry to suggest in (the crop tool's draft); its flips, turn and angle are kept. */
            geometry?: components["schemas"]["Geometry-Input"];
            /**
             * Aspect
             * @description Crop ratio, e.g. '4:5'.
             */
            aspect: string;
            /**
             * @description auto = the frame's orientation; otherwise force the ratio's.
             * @default auto
             */
            orientation: components["schemas"]["Orientation"];
            /** @default centered */
            placement: components["schemas"]["CropPlacement"];
            /**
             * Zoom
             * @description 1 = the largest crop; higher = tighter around the subject.
             * @default 1
             */
            zoom: number;
        };
        /** CurvePoint */
        CurvePoint: {
            /**
             * X
             * @description Input level 0..1.
             */
            x: number;
            /**
             * Y
             * @description Output level 0..1.
             */
            y: number;
        };
        /**
         * DecodeSize
         * @enum {string}
         */
        DecodeSize: "auto" | "full";
        /**
         * DecodeUsed
         * @enum {string}
         */
        DecodeUsed: "half" | "full";
        /**
         * DestinationCheck
         * @description Whether a folder can take exports (checked as the user types it).
         */
        DestinationCheck: {
            /** Path */
            path: string;
            /** Exists */
            exists: boolean;
            /**
             * Ok
             * @description True when an export may write there (the folder is created if needed).
             */
            ok: boolean;
            /**
             * Reason
             * @description Why it can't be used, when ok is false.
             */
            reason: string | null;
        };
        /** DestinationCheckRequest */
        DestinationCheckRequest: {
            /** Path */
            path: string;
        };
        /** Detail */
        "Detail-Input": {
            sharpening?: components["schemas"]["Sharpening-Input"];
            noise_reduction?: components["schemas"]["NoiseReduction-Input"];
        };
        /** Detail */
        "Detail-Output": {
            sharpening: components["schemas"]["Sharpening-Output"];
            noise_reduction: components["schemas"]["NoiseReduction-Output"];
        };
        /**
         * DetectSubjectsRequest
         * @description Detect the photos' main subjects in the background (stored; photos already detected are skipped).
         */
        DetectSubjectsRequest: {
            /** Photo Ids */
            photo_ids: string[];
            /**
             * Kind
             * @default detect_subjects
             * @constant
             */
            kind: "detect_subjects";
        };
        /** DirEntry */
        DirEntry: {
            /** Name */
            name: string;
            /** Path */
            path: string;
            /**
             * Photo Count
             * @description Photos directly in this folder; None if it can't be read.
             */
            photo_count: number | null;
        };
        /** DirListing */
        DirListing: {
            /**
             * Path
             * @description The listed folder; None for the list of drives.
             */
            path: string | null;
            /**
             * Parent
             * @description Folder one level up; None at a drive root or the drive list.
             */
            parent: string | null;
            /**
             * Photo Count
             * @description Photos directly in the listed folder.
             */
            photo_count: number;
            /** Entries */
            entries: components["schemas"]["DirEntry"][];
        };
        /** Effects */
        "Effects-Input": {
            vignette?: components["schemas"]["Vignette-Input"];
            grain?: components["schemas"]["Grain-Input"];
        };
        /** Effects */
        "Effects-Output": {
            vignette: components["schemas"]["Vignette-Output"];
            grain: components["schemas"]["Grain-Output"];
        };
        /**
         * EngineInfo
         * @description What the render engine can do in this version.
         */
        EngineInfo: {
            /** Render Identity */
            render_identity: string;
            /**
             * Later Phase Parameters
             * @description Parameter (or group) prefixes that can't be set yet, with the phase that adds them.
             */
            later_phase_parameters: {
                [key: string]: number;
            };
        };
        /**
         * ExportPlan
         * @description What an export would write (a dry run: nothing is written).
         */
        ExportPlan: {
            /**
             * Destination
             * @description The destination folder, absolute.
             */
            destination: string;
            /** Items */
            items: components["schemas"]["ExportPlanItem"][];
            /**
             * Warnings
             * @description Warnings about the whole export.
             */
            warnings: string[];
        };
        /** ExportPlanItem */
        ExportPlanItem: {
            /** Photo Id */
            photo_id: string;
            /**
             * Filename
             * @description The original's file name.
             */
            filename: string;
            /**
             * Output Name
             * @description File name in the destination.
             */
            output_name: string;
            /** Width */
            width: number;
            /** Height */
            height: number;
            /** @description How the original is decoded for this export. */
            decode: components["schemas"]["DecodeUsed"];
            collision: components["schemas"]["CollisionStatus"];
            /** Warnings */
            warnings: string[];
            /** @description Where the subject the aspect crop frames came from ('none' = centered). Only with the 'subject' anchor. */
            subject: components["schemas"]["SubjectSource"] | null;
            subject_kind: components["schemas"]["SubjectKind"] | null;
            /**
             * Subject Score
             * @description How sure detection is of the subject (none when set by hand).
             */
            subject_score: number | null;
            /**
             * Zoom
             * @description How much tighter than the largest crop (1 = none).
             * @default 1
             */
            zoom: number;
        };
        /** ExportPreset */
        ExportPreset: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /**
             * Description
             * @default
             */
            description: string;
            /** @default custom */
            target: components["schemas"]["ExportTarget"];
            /**
             * Builtin
             * @description Built-in presets can't be edited, only duplicated.
             * @default false
             */
            builtin: boolean;
            settings: components["schemas"]["ExportSettings-Output"];
            /**
             * Version
             * @description +1 on every saved change (for conflict checks).
             * @default 1
             */
            version: number;
            /**
             * Error
             * @description Set when the preset's file can't be read; it can only be deleted then.
             */
            error: string | null;
        };
        /** ExportRequest */
        ExportRequest: {
            /** Photo Ids */
            photo_ids: string[];
            /**
             * Kind
             * @default export
             * @constant
             */
            kind: "export";
            /**
             * Preset Id
             * @description Preset the settings started from (for display).
             */
            preset_id?: string | null;
            settings: components["schemas"]["ExportSettings-Input"];
            /** Destination */
            destination: string;
        };
        /**
         * ExportReview
         * @description A prepared export: what it will write, photo by photo, and the user's decisions so far.
         */
        ExportReview: {
            /** Id */
            id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Preset Id */
            preset_id: string | null;
            /**
             * Style Id
             * @description The style applied before preparing, if any.
             */
            style_id: string | null;
            settings: components["schemas"]["ExportSettings-Output"];
            /**
             * Destination
             * @description The destination folder, absolute.
             */
            destination: string;
            /** Items */
            items: components["schemas"]["ReviewItem"][];
            readonly counts: components["schemas"]["ReviewCounts"];
        };
        /**
         * ExportSettings
         * @description Everything needed to turn an edited photo into an output file.
         */
        "ExportSettings-Input": {
            file?: components["schemas"]["FileSettings-Input"];
            /** @default srgb */
            color_space: components["schemas"]["ColorSpace"];
            size?: components["schemas"]["SizeSettings-Input"];
            aspect?: components["schemas"]["AspectSettings-Input"];
            sharpening?: components["schemas"]["OutputSharpening-Input"];
            metadata?: components["schemas"]["MetadataSettings-Input"];
            naming?: components["schemas"]["NamingSettings-Input"];
            /**
             * Destination
             * @description Default output folder. None = ask every time.
             */
            destination?: string | null;
        };
        /**
         * ExportSettings
         * @description Everything needed to turn an edited photo into an output file.
         */
        "ExportSettings-Output": {
            file: components["schemas"]["FileSettings-Output"];
            /** @default srgb */
            color_space: components["schemas"]["ColorSpace"];
            size: components["schemas"]["SizeSettings-Output"];
            aspect: components["schemas"]["AspectSettings-Output"];
            sharpening: components["schemas"]["OutputSharpening-Output"];
            metadata: components["schemas"]["MetadataSettings-Output"];
            naming: components["schemas"]["NamingSettings-Output"];
            /**
             * Destination
             * @description Default output folder. None = ask every time.
             */
            destination: string | null;
        };
        /**
         * ExportTarget
         * @enum {string}
         */
        ExportTarget: "instagram" | "print" | "web" | "custom";
        /**
         * ExposureFromPhoto
         * @enum {string}
         */
        ExposureFromPhoto: "none" | "value" | "match";
        /**
         * ExposureMetering
         * @enum {string}
         */
        ExposureMetering: "middle" | "highlights" | "camera_settings";
        /**
         * ExposureRule
         * @description Auto exposure: moves a measure of the photo toward a target, so differently exposed photos match.
         */
        "ExposureRule-Input": {
            /**
             * Rule Version
             * @description Format version of this rule type.
             * @default 1
             */
            rule_version: number;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "exposure";
            /**
             * @description What is measured. middle: the median brightness (ordinary scenes). highlights: the white point, so dark subjects (a black cat, night streets) stay dark. camera_settings: the exposure dialed in (shutter, aperture, ISO); evens out a series shot in the same light, needs a group reference.
             * @default middle
             */
            metering: components["schemas"]["ExposureMetering"];
            /**
             * Target
             * @description Target in stops relative to mid gray. None = the metering's default (docs/styles.md).
             */
            target?: number | null;
            /**
             * Use Group
             * @description Target the photo's group reference when it has one ('even out').
             * @default true
             */
            use_group: boolean;
            /**
             * Strength
             * @description How far toward the target, in percent.
             * @default 100
             */
            strength: number;
            /**
             * Max Change
             * @description Largest exposure change in EV either way.
             * @default 1.5
             */
            max_change: number;
        };
        /**
         * ExposureRule
         * @description Auto exposure: moves a measure of the photo toward a target, so differently exposed photos match.
         */
        "ExposureRule-Output": {
            /**
             * Rule Version
             * @description Format version of this rule type.
             * @default 1
             */
            rule_version: number;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "exposure";
            /**
             * @description What is measured. middle: the median brightness (ordinary scenes). highlights: the white point, so dark subjects (a black cat, night streets) stay dark. camera_settings: the exposure dialed in (shutter, aperture, ISO); evens out a series shot in the same light, needs a group reference.
             * @default middle
             */
            metering: components["schemas"]["ExposureMetering"];
            /**
             * Target
             * @description Target in stops relative to mid gray. None = the metering's default (docs/styles.md).
             */
            target: number | null;
            /**
             * Use Group
             * @description Target the photo's group reference when it has one ('even out').
             * @default true
             */
            use_group: boolean;
            /**
             * Strength
             * @description How far toward the target, in percent.
             * @default 100
             */
            strength: number;
            /**
             * Max Change
             * @description Largest exposure change in EV either way.
             * @default 1.5
             */
            max_change: number;
        };
        /**
         * FileFormat
         * @enum {string}
         */
        FileFormat: "jpeg" | "tiff" | "png";
        /** FileSettings */
        "FileSettings-Input": {
            /** @default jpeg */
            format: components["schemas"]["FileFormat"];
            /**
             * Jpeg Quality
             * @default 90
             */
            jpeg_quality: number;
            /**
             * Max File Size Kb
             * @description JPEG only: shrink quality to fit.
             */
            max_file_size_kb?: number | null;
            /**
             * Bit Depth
             * @description 8 or 16 (16 only for TIFF/PNG).
             * @default 8
             */
            bit_depth: number;
            /** @default lzw */
            tiff_compression: components["schemas"]["TiffCompression"];
            /**
             * @description auto = decode a RAW at half size when that still covers the output size; full = always full size.
             * @default auto
             */
            decode: components["schemas"]["DecodeSize"];
        };
        /** FileSettings */
        "FileSettings-Output": {
            /** @default jpeg */
            format: components["schemas"]["FileFormat"];
            /**
             * Jpeg Quality
             * @default 90
             */
            jpeg_quality: number;
            /**
             * Max File Size Kb
             * @description JPEG only: shrink quality to fit.
             */
            max_file_size_kb: number | null;
            /**
             * Bit Depth
             * @description 8 or 16 (16 only for TIFF/PNG).
             * @default 8
             */
            bit_depth: number;
            /** @default lzw */
            tiff_compression: components["schemas"]["TiffCompression"];
            /**
             * @description auto = decode a RAW at half size when that still covers the output size; full = always full size.
             * @default auto
             */
            decode: components["schemas"]["DecodeSize"];
        };
        /**
         * Geometry
         * @description Per-photo framing, applied in this order: flips → quarter turn → straighten → crop.
         */
        "Geometry-Input": {
            crop?: components["schemas"]["CropRect-Input"];
            /**
             * Aspect
             * @description Locked crop aspect ratio, width:height of the crop as shown (e.g. '4:5'). None = free.
             */
            aspect?: string | null;
            /**
             * Angle
             * @description Straighten angle in degrees, clockwise positive, around the center of the frame.
             * @default 0
             */
            angle: number;
            /**
             * Rotate
             * @description Quarter turn clockwise in degrees (0, 90, 180, 270), after the flips.
             * @default 0
             * @enum {integer}
             */
            rotate: 0 | 90 | 180 | 270;
            /**
             * Flip Horizontal
             * @description Mirror left-right (before the quarter turn).
             * @default false
             */
            flip_horizontal: boolean;
            /**
             * Flip Vertical
             * @description Mirror top-bottom (before the quarter turn).
             * @default false
             */
            flip_vertical: boolean;
        };
        /**
         * Geometry
         * @description Per-photo framing, applied in this order: flips → quarter turn → straighten → crop.
         */
        "Geometry-Output": {
            crop: components["schemas"]["CropRect-Output"];
            /**
             * Aspect
             * @description Locked crop aspect ratio, width:height of the crop as shown (e.g. '4:5'). None = free.
             */
            aspect: string | null;
            /**
             * Angle
             * @description Straighten angle in degrees, clockwise positive, around the center of the frame.
             * @default 0
             */
            angle: number;
            /**
             * Rotate
             * @description Quarter turn clockwise in degrees (0, 90, 180, 270), after the flips.
             * @default 0
             * @enum {integer}
             */
            rotate: 0 | 90 | 180 | 270;
            /**
             * Flip Horizontal
             * @description Mirror left-right (before the quarter turn).
             * @default false
             */
            flip_horizontal: boolean;
            /**
             * Flip Vertical
             * @description Mirror top-bottom (before the quarter turn).
             * @default false
             */
            flip_vertical: boolean;
        };
        /**
         * GeometryChange
         * @description A change to a photo's geometry; only the fields given change.
         *
         *     Core applies them in this order: reset, flips, quarter turn, angle, aspect, crop. Flips and quarter turns
         *     carry the crop along (it keeps framing the same content), and a flip mirrors the angle. After a change of
         *     angle or aspect the crop is shrunk around its center until it fits the straightened image; a crop given
         *     explicitly is checked as is and rejected if it doesn't fit.
         */
        GeometryChange: {
            /**
             * Reset
             * @description Start from the original framing.
             * @default false
             */
            reset: boolean;
            /** Flip Horizontal */
            flip_horizontal?: boolean | null;
            /** Flip Vertical */
            flip_vertical?: boolean | null;
            /** Rotate */
            rotate?: (0 | 90 | 180 | 270) | null;
            /** Angle */
            angle?: number | null;
            /**
             * Aspect
             * @description Lock this crop aspect ratio; send null explicitly to unlock (free).
             */
            aspect?: string | null;
            crop?: components["schemas"]["CropRect-Input"] | null;
        };
        /**
         * GeometryPreviewRequest
         * @description A geometry and a change to try on it (nothing is saved).
         */
        GeometryPreviewRequest: {
            geometry: components["schemas"]["Geometry-Input"];
            change: components["schemas"]["GeometryChange"];
        };
        /** GradeWheel */
        "GradeWheel-Input": {
            /**
             * Hue
             * @description Tint hue in degrees.
             * @default 0
             */
            hue: number;
            /**
             * Saturation
             * @description Tint strength.
             * @default 0
             */
            saturation: number;
            /**
             * Luminance
             * @description Brightness of this tonal range.
             * @default 0
             */
            luminance: number;
        };
        /** GradeWheel */
        "GradeWheel-Output": {
            /**
             * Hue
             * @description Tint hue in degrees.
             * @default 0
             */
            hue: number;
            /**
             * Saturation
             * @description Tint strength.
             * @default 0
             */
            saturation: number;
            /**
             * Luminance
             * @description Brightness of this tonal range.
             * @default 0
             */
            luminance: number;
        };
        /** Grain */
        "Grain-Input": {
            /**
             * Amount
             * @description Film grain strength (planned for Phase 9).
             * @default 0
             */
            amount: number;
            /**
             * Size
             * @description Grain size.
             * @default 25
             */
            size: number;
            /**
             * Roughness
             * @description Grain irregularity.
             * @default 50
             */
            roughness: number;
        };
        /** Grain */
        "Grain-Output": {
            /**
             * Amount
             * @description Film grain strength (planned for Phase 9).
             * @default 0
             */
            amount: number;
            /**
             * Size
             * @description Grain size.
             * @default 25
             */
            size: number;
            /**
             * Roughness
             * @description Grain irregularity.
             * @default 50
             */
            roughness: number;
        };
        /**
         * GroupReference
         * @description The group a photo was evened out with: the group's medians of every exposure measure. It's stored with
         *     the photo's edit, so the photo's render doesn't depend on what is selected later, and any metering mode of
         *     the style can use it.
         */
        GroupReference: {
            /**
             * Id
             * @description Shared by the photos applied together.
             */
            id: string;
            /**
             * Size
             * @description Number of photos in the group.
             */
            size: number;
            /**
             * Middle
             * @description Median of the photos' middles.
             */
            middle: number | null;
            /**
             * White
             * @description Median of their white points.
             */
            white: number | null;
            /**
             * Camera Ev
             * @description Median EV100 of those with exposure settings in EXIF.
             */
            camera_ev: number | null;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** Health */
        Health: {
            /** Status */
            status: string;
            /** Version */
            version: string;
        };
        /** Hsl */
        "Hsl-Input": {
            red?: components["schemas"]["HslBand-Input"];
            orange?: components["schemas"]["HslBand-Input"];
            yellow?: components["schemas"]["HslBand-Input"];
            green?: components["schemas"]["HslBand-Input"];
            aqua?: components["schemas"]["HslBand-Input"];
            blue?: components["schemas"]["HslBand-Input"];
            purple?: components["schemas"]["HslBand-Input"];
            magenta?: components["schemas"]["HslBand-Input"];
        };
        /** Hsl */
        "Hsl-Output": {
            red: components["schemas"]["HslBand-Output"];
            orange: components["schemas"]["HslBand-Output"];
            yellow: components["schemas"]["HslBand-Output"];
            green: components["schemas"]["HslBand-Output"];
            aqua: components["schemas"]["HslBand-Output"];
            blue: components["schemas"]["HslBand-Output"];
            purple: components["schemas"]["HslBand-Output"];
            magenta: components["schemas"]["HslBand-Output"];
        };
        /** HslBand */
        "HslBand-Input": {
            /**
             * Hue
             * @description Shift hue of this color band.
             * @default 0
             */
            hue: number;
            /**
             * Saturation
             * @description Saturation of this color band.
             * @default 0
             */
            saturation: number;
            /**
             * Luminance
             * @description Brightness of this color band.
             * @default 0
             */
            luminance: number;
        };
        /** HslBand */
        "HslBand-Output": {
            /**
             * Hue
             * @description Shift hue of this color band.
             * @default 0
             */
            hue: number;
            /**
             * Saturation
             * @description Saturation of this color band.
             * @default 0
             */
            saturation: number;
            /**
             * Luminance
             * @description Brightness of this color band.
             * @default 0
             */
            luminance: number;
        };
        /** ImportRequest */
        ImportRequest: {
            /**
             * Folder
             * @description Absolute path of the photo folder to import (read-only).
             */
            folder: string;
            /**
             * Include Subfolders
             * @default false
             */
            include_subfolders: boolean;
        };
        /** Job */
        Job: {
            /** Id */
            id: string;
            kind: components["schemas"]["JobKind"];
            status: components["schemas"]["JobStatus"];
            /**
             * Title
             * @description Human-readable summary, e.g. 'Apply Moody Forest to 12 photos'.
             */
            title: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Finished At */
            finished_at: string | null;
            /** Progress */
            progress: number;
            /** Total */
            total: number;
            /** Completed */
            completed: number;
            /**
             * Failed
             * @default 0
             */
            failed: number;
            /** Style Id */
            style_id: string | null;
            /** Preset Id */
            preset_id: string | null;
            /** Destination */
            destination: string | null;
            /**
             * Folder
             * @description Photo folder an import job reads (read-only).
             */
            folder: string | null;
            /**
             * Summary
             * @description Outcome in one line, e.g. '67 new, 1 skipped'.
             */
            summary: string | null;
            /**
             * Review Id
             * @description The review a prepare_export job created.
             */
            review_id: string | null;
            /** Items */
            items: components["schemas"]["JobItem"][];
        };
        /** JobItem */
        JobItem: {
            /**
             * Photo Id
             * @description None while an import hasn't identified the file yet.
             */
            photo_id: string | null;
            /** Filename */
            filename: string;
            status: components["schemas"]["JobStatus"];
            /** Message */
            message: string | null;
            /** Output Path */
            output_path: string | null;
            /**
             * Output Bytes
             * @description Size of the written file (exports).
             */
            output_bytes: number | null;
            /** Output Width */
            output_width: number | null;
            /** Output Height */
            output_height: number | null;
            /** Warnings */
            warnings: string[];
        };
        /**
         * JobKind
         * @enum {string}
         */
        JobKind: "import" | "render" | "apply_style" | "export" | "apply_and_export" | "detect_subjects" | "prepare_export";
        /**
         * JobStatus
         * @enum {string}
         */
        JobStatus: "queued" | "running" | "done" | "failed" | "cancelled";
        /** Lens */
        "Lens-Input": {
            /**
             * Profile Corrections
             * @description Apply lens distortion/vignetting profile.
             * @default false
             */
            profile_corrections: boolean;
            /**
             * Remove Chromatic Aberration
             * @default false
             */
            remove_chromatic_aberration: boolean;
        };
        /** Lens */
        "Lens-Output": {
            /**
             * Profile Corrections
             * @description Apply lens distortion/vignetting profile.
             * @default false
             */
            profile_corrections: boolean;
            /**
             * Remove Chromatic Aberration
             * @default false
             */
            remove_chromatic_aberration: boolean;
        };
        /**
         * LibraryFolder
         * @description A folder that has been imported into the catalog.
         */
        LibraryFolder: {
            /** Path */
            path: string;
            /** Include Subfolders */
            include_subfolders: boolean;
            /** Photo Count */
            photo_count: number;
            /** Last Imported At */
            last_imported_at: string | null;
        };
        /** LibraryInfo */
        LibraryInfo: {
            /**
             * Folder
             * @description Currently opened photo folder.
             */
            folder: string | null;
            /**
             * Include Subfolders
             * @description The Library also shows photos in subfolders.
             * @default false
             */
            include_subfolders: boolean;
            /** Photo Count */
            photo_count: number;
            /**
             * Suggested Folder
             * @description Folder to offer when nothing is open yet (the configured sample folder).
             */
            suggested_folder: string | null;
        };
        /**
         * MetadataPolicy
         * @enum {string}
         */
        MetadataPolicy: "all" | "copyright_only" | "copyright_and_contact" | "all_except_camera_and_gps";
        /** MetadataSettings */
        "MetadataSettings-Input": {
            /** @default all_except_camera_and_gps */
            policy: components["schemas"]["MetadataPolicy"];
            /**
             * Strip Gps
             * @description Only matters for policy 'all'; the others never write GPS.
             * @default true
             */
            strip_gps: boolean;
            /**
             * Copyright
             * @description Copyright notice; {year} = the photo's capture year. None = the configured default.
             */
            copyright?: string | null;
            /**
             * Creator
             * @description None = the configured default.
             */
            creator?: string | null;
            /** Keywords */
            keywords?: string[];
        };
        /** MetadataSettings */
        "MetadataSettings-Output": {
            /** @default all_except_camera_and_gps */
            policy: components["schemas"]["MetadataPolicy"];
            /**
             * Strip Gps
             * @description Only matters for policy 'all'; the others never write GPS.
             * @default true
             */
            strip_gps: boolean;
            /**
             * Copyright
             * @description Copyright notice; {year} = the photo's capture year. None = the configured default.
             */
            copyright: string | null;
            /**
             * Creator
             * @description None = the configured default.
             */
            creator: string | null;
            /** Keywords */
            keywords: string[];
        };
        /** NamingSettings */
        "NamingSettings-Input": {
            /**
             * Template
             * @description Tokens: {original} {date} {time} {seq} {seq:03} {style} {preset} {camera}. The extension comes from the file format.
             * @default {original}
             */
            template: string;
            /** @default suffix */
            on_collision: components["schemas"]["CollisionPolicy"];
        };
        /** NamingSettings */
        "NamingSettings-Output": {
            /**
             * Template
             * @description Tokens: {original} {date} {time} {seq} {seq:03} {style} {preset} {camera}. The extension comes from the file format.
             * @default {original}
             */
            template: string;
            /** @default suffix */
            on_collision: components["schemas"]["CollisionPolicy"];
        };
        /** NoiseReduction */
        "NoiseReduction-Input": {
            /**
             * Luminance
             * @description Luminance noise reduction (planned for Phase 9).
             * @default 0
             */
            luminance: number;
            /**
             * Color
             * @description Color noise reduction (planned for Phase 9).
             * @default 25
             */
            color: number;
        };
        /** NoiseReduction */
        "NoiseReduction-Output": {
            /**
             * Luminance
             * @description Luminance noise reduction (planned for Phase 9).
             * @default 0
             */
            luminance: number;
            /**
             * Color
             * @description Color noise reduction (planned for Phase 9).
             * @default 25
             */
            color: number;
        };
        /** OpenFolderRequest */
        OpenFolderRequest: {
            /**
             * Folder
             * @description An already imported folder to show in the Library.
             */
            folder: string;
        };
        /**
         * Orientation
         * @enum {string}
         */
        Orientation: "auto" | "portrait" | "landscape";
        /** OutputSharpening */
        "OutputSharpening-Input": {
            /** @default screen */
            target: components["schemas"]["SharpenFor"];
            /** @default standard */
            amount: components["schemas"]["SharpenAmount"];
        };
        /** OutputSharpening */
        "OutputSharpening-Output": {
            /** @default screen */
            target: components["schemas"]["SharpenFor"];
            /** @default standard */
            amount: components["schemas"]["SharpenAmount"];
        };
        /** Page[Photo] */
        Page_Photo_: {
            /** Items */
            items: components["schemas"]["Photo"][];
            /** Total */
            total: number;
            /** Offset */
            offset: number;
            /** Limit */
            limit: number;
        };
        /**
         * Photo
         * @description A source photo known to the catalog. The file itself is never modified.
         */
        Photo: {
            /**
             * Id
             * @description Stable catalog id.
             */
            id: string;
            /**
             * Path
             * @description Absolute path of the original file (read-only).
             */
            path: string;
            /** Filename */
            filename: string;
            /** Folder */
            folder: string;
            /**
             * File Size
             * @description Bytes.
             */
            file_size: number;
            /** Captured At */
            captured_at: string | null;
            /**
             * Camera
             * @description Camera make and model, e.g. 'FUJIFILM X-T3'.
             */
            camera: string | null;
            /** Lens */
            lens: string | null;
            /** Iso */
            iso: number | null;
            /**
             * Shutter
             * @description Exposure time as displayed, e.g. '1/250'.
             */
            shutter: string | null;
            /**
             * Aperture
             * @description f-number.
             */
            aperture: number | null;
            /**
             * Focal Length
             * @description Millimetres.
             */
            focal_length: number | null;
            /**
             * Width
             * @description Pixel width after orientation.
             */
            width: number;
            /**
             * Height
             * @description Pixel height after orientation.
             */
            height: number;
            /**
             * Edited Width
             * @description Pixel width after the edit's geometry (crop, quarter turn).
             */
            edited_width: number;
            /**
             * Edited Height
             * @description Pixel height after the edit's geometry.
             */
            edited_height: number;
            /**
             * Rating
             * @default 0
             */
            rating: number;
            /**
             * Style Id
             * @description Style assigned to this photo, if any.
             */
            style_id: string | null;
            /**
             * Has Overrides
             * @description Per-photo adjustments on top of the style.
             * @default false
             */
            has_overrides: boolean;
            /**
             * Sidecar Jpeg
             * @description Camera JPEG saved next to a RAW original (read-only), if any.
             */
            sidecar_jpeg: string | null;
            /**
             * Image Version
             * @description Changes whenever the photo renders differently; add it to image URLs.
             * @default
             */
            image_version: string;
        };
        /** PhotoDetail */
        PhotoDetail: {
            photo: components["schemas"]["Photo"];
            edit: components["schemas"]["PhotoEdit"];
            /** @description None if the camera recorded no white balance. */
            as_shot: components["schemas"]["AsShot"] | null;
        };
        /**
         * PhotoEdit
         * @description The edit of one photo: an optional style plus per-photo overrides. Overrides always win.
         */
        PhotoEdit: {
            /** Photo Id */
            photo_id: string;
            /** Style Id */
            style_id: string | null;
            /** @description Effective adjustments (style + overrides). */
            adjustments: components["schemas"]["AdjustmentParams-Output"];
            /**
             * Overridden
             * @description Dotted parameter names that are overridden per photo, e.g. 'tone.exposure'.
             */
            overridden: string[];
            /**
             * Revision
             * @description Changes whenever the edit changes.
             * @default
             */
            revision: string;
            /** @description What a reset goes back to: the style's values when the photo has a style, else the unedited parameters (JPEGs start unsharpened). */
            defaults: components["schemas"]["AdjustmentParams-Output"];
            /** @description The photo's parameters with no style and no tweaks (the 'Before' look). */
            unedited: components["schemas"]["AdjustmentParams-Output"];
            /**
             * Style Values
             * @description Dotted parameter names whose value comes from the style (incl. its rules).
             */
            style_values: string[];
            /**
             * Rules
             * @description What the style's rules did on this photo.
             */
            rules: components["schemas"]["RuleResult"][];
            /**
             * Style Version
             * @description Version of the style the edit uses.
             */
            style_version: number | null;
            /**
             * Style Error
             * @description Why the assigned style isn't applied (missing or invalid), if it isn't.
             */
            style_error: string | null;
            /** @description Set by 'even out' when the style was applied. */
            group: components["schemas"]["GroupReference"] | null;
        };
        /**
         * PhotoMeasurements
         * @description Measurements of one render: brightness in stops relative to mid gray, white balance in Kelvin/tint.
         */
        PhotoMeasurements: {
            /**
             * Middle
             * @description Median brightness.
             */
            middle: number | null;
            /**
             * White
             * @description White point (99.5th percentile).
             */
            white: number | null;
            /** Temperature */
            temperature: number | null;
            /** Tint */
            tint: number | null;
        };
        /**
         * PhotoSort
         * @enum {string}
         */
        PhotoSort: "date" | "name" | "rating";
        /** PhotoStyleRequest */
        PhotoStyleRequest: {
            /**
             * Style Id
             * @description None removes the photo's style.
             */
            style_id: string | null;
        };
        /**
         * PrepareExportRequest
         * @description Prepare an export for review (Phase 6c): optionally apply a style first, then frame and sort every
         *     photo into Ready and Check. The job's ``review_id`` names the review.
         */
        PrepareExportRequest: {
            /** Photo Ids */
            photo_ids: string[];
            /**
             * Kind
             * @default prepare_export
             * @constant
             */
            kind: "prepare_export";
            /**
             * Style Id
             * @description Apply this style first; None = keep the edits.
             */
            style_id?: string | null;
            /**
             * Even Out
             * @default false
             */
            even_out: boolean;
            /** Preset Id */
            preset_id?: string | null;
            settings: components["schemas"]["ExportSettings-Input"];
            /** Destination */
            destination: string;
        };
        /** Presence */
        "Presence-Input": {
            /**
             * Vibrance
             * @description Saturation boost weighted toward muted colors.
             * @default 0
             */
            vibrance: number;
            /**
             * Saturation
             * @description Uniform saturation.
             * @default 0
             */
            saturation: number;
            /**
             * Clarity
             * @description Midtone local contrast (planned for Phase 9).
             * @default 0
             */
            clarity: number;
            /**
             * Texture
             * @description Fine-detail local contrast (planned for Phase 9).
             * @default 0
             */
            texture: number;
            /**
             * Dehaze
             * @description Remove (+) or add (-) atmospheric haze (planned for Phase 9).
             * @default 0
             */
            dehaze: number;
        };
        /** Presence */
        "Presence-Output": {
            /**
             * Vibrance
             * @description Saturation boost weighted toward muted colors.
             * @default 0
             */
            vibrance: number;
            /**
             * Saturation
             * @description Uniform saturation.
             * @default 0
             */
            saturation: number;
            /**
             * Clarity
             * @description Midtone local contrast (planned for Phase 9).
             * @default 0
             */
            clarity: number;
            /**
             * Texture
             * @description Fine-detail local contrast (planned for Phase 9).
             * @default 0
             */
            texture: number;
            /**
             * Dehaze
             * @description Remove (+) or add (-) atmospheric haze (planned for Phase 9).
             * @default 0
             */
            dehaze: number;
        };
        /** PresetCreate */
        PresetCreate: {
            /** Name */
            name: string;
            /**
             * Description
             * @default
             */
            description: string;
            /** @default custom */
            target: components["schemas"]["ExportTarget"];
            settings?: components["schemas"]["ExportSettings-Input"];
        };
        /** PresetDuplicate */
        PresetDuplicate: {
            /**
             * Name
             * @description Default: '<name> copy'.
             */
            name?: string | null;
        };
        /**
         * PresetUpdate
         * @description Fields left out stay as they are.
         */
        PresetUpdate: {
            /**
             * Expected Version
             * @description The version the change was made on.
             */
            expected_version: number;
            /** Name */
            name?: string | null;
            /** Description */
            description?: string | null;
            target?: components["schemas"]["ExportTarget"] | null;
            settings?: components["schemas"]["ExportSettings-Input"] | null;
        };
        /** ReportPhoto */
        ReportPhoto: {
            /** Photo Id */
            photo_id: string;
            /** Filename */
            filename: string;
            /**
             * Camera Ev
             * @description Exposure dialed in (EV100) from EXIF.
             */
            camera_ev: number | null;
            before: components["schemas"]["PhotoMeasurements"];
            after: components["schemas"]["PhotoMeasurements"];
            /** Rules */
            rules: components["schemas"]["RuleResult"][];
            /**
             * Deviation
             * @description Distance of 'after' middle from the set's median, in stops.
             */
            deviation: number;
        };
        /**
         * ResizeMode
         * @enum {string}
         */
        ResizeMode: "original" | "long_edge" | "short_edge" | "width_height" | "megapixels" | "percentage";
        /** RevealRequest */
        RevealRequest: {
            /**
             * Path
             * @description A file exported in this session.
             */
            path: string;
        };
        /** ReviewCandidate */
        ReviewCandidate: {
            /**
             * Index
             * @description Position in the photo's detected candidates (to choose it).
             */
            index: number;
            /** @description Normalized to the edited photo. */
            box: components["schemas"]["SubjectBox"];
            kind: components["schemas"]["SubjectKind"];
            /** Score */
            score: number;
            /** Label */
            label: string | null;
            /**
             * Chosen
             * @description This candidate is the subject the crop frames.
             * @default false
             */
            chosen: boolean;
        };
        /** ReviewCounts */
        ReviewCounts: {
            /** Total */
            total: number;
            /** Ready */
            ready: number;
            /**
             * Check
             * @description Check photos not approved yet.
             */
            check: number;
            /**
             * Approved
             * @description Check photos the user approved.
             */
            approved: number;
            /** Unusable */
            unusable: number;
        };
        /** ReviewExportRequest */
        ReviewExportRequest: {
            /** @default approved */
            scope: components["schemas"]["ReviewExportScope"];
        };
        /**
         * ReviewExportScope
         * @enum {string}
         */
        ReviewExportScope: "approved" | "all";
        /** ReviewItem */
        ReviewItem: {
            /** Photo Id */
            photo_id: string;
            /** Filename */
            filename: string;
            status: components["schemas"]["ReviewStatus"];
            /** Reasons */
            reasons: components["schemas"]["ReviewReason"][];
            /**
             * Approved
             * @description The user approved this framing (Check photos).
             * @default false
             */
            approved: boolean;
            /**
             * Approved Framing
             * @description The framing the approval was given for; a different one drops it.
             */
            approved_framing: string | null;
            /**
             * Framing
             * @description Identifies the framing (crop, output size, subject) to compare.
             */
            framing: string;
            /** @default none */
            subject: components["schemas"]["SubjectSource"];
            subject_kind: components["schemas"]["SubjectKind"] | null;
            /** Subject Score */
            subject_score: number | null;
            /** @description Normalized to the edited photo. */
            subject_box: components["schemas"]["SubjectBox"] | null;
            /** Candidates */
            candidates: components["schemas"]["ReviewCandidate"][];
            /** @description The export's crop, normalized to the edited photo. */
            crop: components["schemas"]["CropRect-Output"];
            /**
             * Zoom
             * @description The zoom the export uses.
             */
            zoom: number;
            /**
             * Auto Zoom
             * @description What automatic zoom chose (1 when it is off or not used).
             */
            auto_zoom: number;
            /**
             * Zoom Override
             * @description Set in the review.
             */
            zoom_override: number | null;
            limits: components["schemas"]["ZoomLimits"];
            decode: components["schemas"]["DecodeUsed"];
            /**
             * Width
             * @description Output width.
             */
            width: number;
            /**
             * Height
             * @description Output height.
             */
            height: number;
            /** Warnings */
            warnings: string[];
            /**
             * Revision
             * @description Changes whenever the framing preview changes (for caching).
             */
            revision: string;
        };
        /**
         * ReviewItemUpdate
         * @description Fields left out stay as they are. ``zoom: null`` goes back to the automatic zoom.
         */
        ReviewItemUpdate: {
            /** Zoom */
            zoom?: number | null;
            /** Approved */
            approved?: boolean | null;
        };
        /** ReviewReason */
        ReviewReason: {
            code: components["schemas"]["ReviewRule"];
            /**
             * Text
             * @description The reason in words, for this photo.
             */
            text: string;
        };
        /**
         * ReviewRule
         * @enum {string}
         */
        ReviewRule: "no_subject" | "uncertain" | "ambiguous" | "cut_off" | "zoom_limit" | "changed" | "unusable";
        /**
         * ReviewSettings
         * @description How strict the review is: which rules put a photo in Check, and their thresholds.
         */
        "ReviewSettings-Input": {
            /**
             * No Subject
             * @description Check photos without a recognized subject.
             * @default true
             */
            no_subject: boolean;
            /**
             * Uncertain
             * @description Check detected subjects scoring below min_score.
             * @default true
             */
            uncertain: boolean;
            /**
             * Min Score
             * @description The lowest score trusted without a look.
             * @default 0.5
             */
            min_score: number;
            /**
             * Ambiguous
             * @description Check photos with a rival nearly as good.
             * @default true
             */
            ambiguous: boolean;
            /**
             * Ambiguity
             * @description A rival scoring at least this share of the subject's score makes the photo ambiguous.
             * @default 0.75
             */
            ambiguity: number;
            /**
             * Cut Off
             * @description Check photos whose crop can't hold the whole subject.
             * @default true
             */
            cut_off: boolean;
            /**
             * Zoom Limit
             * @description Check photos whose subject stays too small even at the quality limit.
             * @default true
             */
            zoom_limit: boolean;
        };
        /**
         * ReviewSettings
         * @description How strict the review is: which rules put a photo in Check, and their thresholds.
         */
        "ReviewSettings-Output": {
            /**
             * No Subject
             * @description Check photos without a recognized subject.
             * @default true
             */
            no_subject: boolean;
            /**
             * Uncertain
             * @description Check detected subjects scoring below min_score.
             * @default true
             */
            uncertain: boolean;
            /**
             * Min Score
             * @description The lowest score trusted without a look.
             * @default 0.5
             */
            min_score: number;
            /**
             * Ambiguous
             * @description Check photos with a rival nearly as good.
             * @default true
             */
            ambiguous: boolean;
            /**
             * Ambiguity
             * @description A rival scoring at least this share of the subject's score makes the photo ambiguous.
             * @default 0.75
             */
            ambiguity: number;
            /**
             * Cut Off
             * @description Check photos whose crop can't hold the whole subject.
             * @default true
             */
            cut_off: boolean;
            /**
             * Zoom Limit
             * @description Check photos whose subject stays too small even at the quality limit.
             * @default true
             */
            zoom_limit: boolean;
        };
        /**
         * ReviewStatus
         * @enum {string}
         */
        ReviewStatus: "ready" | "check" | "unusable";
        /**
         * ReviewSubjectUpdate
         * @description Choose a detected candidate (``candidate``), draw a box (``box``, normalized to the edited photo), or
         *     ``box: null`` to go back to the detected subject.
         */
        ReviewSubjectUpdate: {
            /** Candidate */
            candidate?: number | null;
            box?: components["schemas"]["SubjectBox"] | null;
        };
        /** ReviewSummary */
        ReviewSummary: {
            /** Id */
            id: string;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Preset Id */
            preset_id: string | null;
            /** Destination */
            destination: string;
            counts: components["schemas"]["ReviewCounts"];
        };
        /** RuleChange */
        RuleChange: {
            /** Type */
            type: string;
            /**
             * Before
             * @description None = no such rule in that version.
             */
            before: {
                [key: string]: unknown;
            } | null;
            /** After */
            after: {
                [key: string]: unknown;
            } | null;
        };
        /**
         * RuleResult
         * @description What one rule did on one photo (for display, reports and the AI).
         */
        RuleResult: {
            /** Type */
            type: string;
            /**
             * Summary
             * @description One line, e.g. 'middle -2.1 → target -1.0 stops: +1.1 EV'.
             */
            summary: string;
            /** Measured */
            measured: number | null;
            /** Target */
            target: number | null;
            /**
             * Values
             * @description Parameters the rule set, e.g. {'tone.exposure': 0.6}.
             */
            values: {
                [key: string]: number;
            };
            /**
             * Note
             * @description Why the rule fell back or was limited, if it did.
             */
            note: string | null;
        };
        /**
         * SharpenAmount
         * @enum {string}
         */
        SharpenAmount: "low" | "standard" | "high";
        /**
         * SharpenFor
         * @enum {string}
         */
        SharpenFor: "none" | "screen" | "matte_paper" | "glossy_paper";
        /** Sharpening */
        "Sharpening-Input": {
            /**
             * Amount
             * @description Sharpening strength.
             * @default 40
             */
            amount: number;
            /**
             * Radius
             * @description Edge width in pixels.
             * @default 1
             */
            radius: number;
            /**
             * Detail
             * @description How much fine detail is sharpened.
             * @default 25
             */
            detail: number;
            /**
             * Masking
             * @description Limit sharpening to edges (higher = fewer areas).
             * @default 0
             */
            masking: number;
        };
        /** Sharpening */
        "Sharpening-Output": {
            /**
             * Amount
             * @description Sharpening strength.
             * @default 40
             */
            amount: number;
            /**
             * Radius
             * @description Edge width in pixels.
             * @default 1
             */
            radius: number;
            /**
             * Detail
             * @description How much fine detail is sharpened.
             * @default 25
             */
            detail: number;
            /**
             * Masking
             * @description Limit sharpening to edges (higher = fewer areas).
             * @default 0
             */
            masking: number;
        };
        /** SizeSettings */
        "SizeSettings-Input": {
            /** @default original */
            mode: components["schemas"]["ResizeMode"];
            /**
             * Long Edge
             * @description Pixels (mode=long_edge).
             */
            long_edge?: number | null;
            /**
             * Short Edge
             * @description Pixels (mode=short_edge).
             */
            short_edge?: number | null;
            /**
             * Width
             * @description Pixels (mode=width_height).
             */
            width?: number | null;
            /**
             * Height
             * @description Pixels (mode=width_height).
             */
            height?: number | null;
            /** Megapixels */
            megapixels?: number | null;
            /** Percentage */
            percentage?: number | null;
            /**
             * Dont Enlarge
             * @default true
             */
            dont_enlarge: boolean;
            /**
             * Ppi
             * @description Print resolution stored in the file.
             * @default 300
             */
            ppi: number;
        };
        /** SizeSettings */
        "SizeSettings-Output": {
            /** @default original */
            mode: components["schemas"]["ResizeMode"];
            /**
             * Long Edge
             * @description Pixels (mode=long_edge).
             */
            long_edge: number | null;
            /**
             * Short Edge
             * @description Pixels (mode=short_edge).
             */
            short_edge: number | null;
            /**
             * Width
             * @description Pixels (mode=width_height).
             */
            width: number | null;
            /**
             * Height
             * @description Pixels (mode=width_height).
             */
            height: number | null;
            /** Megapixels */
            megapixels: number | null;
            /** Percentage */
            percentage: number | null;
            /**
             * Dont Enlarge
             * @default true
             */
            dont_enlarge: boolean;
            /**
             * Ppi
             * @description Print resolution stored in the file.
             * @default 300
             */
            ppi: number;
        };
        /**
         * SortOrder
         * @enum {string}
         */
        SortOrder: "asc" | "desc";
        /**
         * Spread
         * @description How far apart one measurement is across the set (smaller = more consistent).
         */
        Spread: {
            /** Measure */
            measure: string;
            /**
             * Before Mad
             * @description Median absolute deviation before the style.
             */
            before_mad: number;
            /** After Mad */
            after_mad: number;
            /**
             * Before Range
             * @description Largest minus smallest before the style.
             */
            before_range: number;
            /** After Range */
            after_range: number;
        };
        /**
         * StyleCreate
         * @description A new style from explicit values (creating one from a photo uses ``StyleFromPhoto``).
         */
        StyleCreate: {
            /** Name */
            name: string;
            /**
             * Description
             * @default
             */
            description: string;
            /** Best For */
            best_for?: string[];
            /** Avoid On */
            avoid_on?: string[];
            /** Values */
            values?: {
                [key: string]: unknown;
            };
            /** Rules */
            rules?: (components["schemas"]["ExposureRule-Input"] | components["schemas"]["WhiteBalanceRule-Input"])[];
            /** Test Photo Ids */
            test_photo_ids?: string[];
        };
        /** StyleDeleted */
        StyleDeleted: {
            /** Id */
            id: string;
            /**
             * Photos
             * @description Photos that dropped back to no style (their tweaks are kept).
             */
            photos: number;
        };
        /**
         * StyleDiff
         * @description What differs between two versions of a style.
         */
        StyleDiff: {
            /** Style Id */
            style_id: string;
            /** A */
            a: number;
            /** B */
            b: number;
            /** Values */
            values: components["schemas"]["ValueChange"][];
            /** Rules */
            rules: components["schemas"]["RuleChange"][];
            /**
             * Fields
             * @description Other changed fields (name, description, test set, …).
             */
            fields: string[];
            /** Same Look */
            same_look: boolean;
        };
        /** StyleDuplicate */
        StyleDuplicate: {
            /**
             * Name
             * @description Default: '<name> (copy)'.
             */
            name?: string | null;
        };
        /**
         * StyleFromPhoto
         * @description Create a style from a photo's current look.
         */
        StyleFromPhoto: {
            /** Photo Id */
            photo_id: string;
            /** Name */
            name: string;
            /**
             * Description
             * @default
             */
            description: string;
            /**
             * Groups
             * @description Which parameter groups to take.
             */
            groups?: components["schemas"]["AdjustmentGroup"][];
            /** @default match */
            exposure: components["schemas"]["ExposureFromPhoto"];
            /** @default offset */
            white_balance: components["schemas"]["WhiteBalanceFromPhoto"];
        };
        /** StyleReportRequest */
        StyleReportRequest: {
            /**
             * Photo Ids
             * @description None = the style's test set, else the photos using it.
             */
            photo_ids?: string[] | null;
        };
        /** StyleRevert */
        StyleRevert: {
            /**
             * Version
             * @description The version whose look and text come back (as a new version).
             */
            version: number;
            /** Expected Version */
            expected_version: number;
        };
        /** StyleSampleView */
        StyleSampleView: {
            /** Photo Id */
            photo_id: string;
            /** Caption */
            caption: string;
            /** Before Url */
            before_url: string;
            /** After Url */
            after_url: string;
            /**
             * Stale
             * @description Rendered with an older look of the style.
             */
            stale: boolean;
        };
        /** StyleSamplesRequest */
        StyleSamplesRequest: {
            /** Photo Ids */
            photo_ids: string[];
        };
        /** StyleSummary */
        StyleSummary: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /**
             * Description
             * @default
             */
            description: string;
            /**
             * Cover Url
             * @description The first sample's 'after' image, if any.
             */
            cover_url: string | null;
            /** Updated At */
            updated_at: string | null;
            /**
             * Version
             * @default 1
             */
            version: number;
            /**
             * Photo Count
             * @description Photos that use this style.
             * @default 0
             */
            photo_count: number;
            /**
             * Error
             * @description Why the style file can't be used, if it can't.
             */
            error: string | null;
        };
        /**
         * StyleUpdate
         * @description A change to a style. Fields left out stay as they are.
         */
        StyleUpdate: {
            /**
             * Expected Version
             * @description The version the change is based on (conflict if newer).
             */
            expected_version: number;
            /**
             * Change Note
             * @default
             */
            change_note: string;
            /** Name */
            name?: string | null;
            /** Description */
            description?: string | null;
            /** Best For */
            best_for?: string[] | null;
            /** Avoid On */
            avoid_on?: string[] | null;
            /** Values */
            values?: {
                [key: string]: unknown;
            } | null;
            /** Rules */
            rules?: (components["schemas"]["ExposureRule-Input"] | components["schemas"]["WhiteBalanceRule-Input"])[] | null;
            /** Test Photo Ids */
            test_photo_ids?: string[] | null;
        };
        /**
         * StyleUpdateFromPhoto
         * @description Replace the given groups of a style with a photo's values.
         */
        StyleUpdateFromPhoto: {
            /** Photo Id */
            photo_id: string;
            /** Groups */
            groups: components["schemas"]["AdjustmentGroup"][];
            /** Expected Version */
            expected_version: number;
            /**
             * Change Note
             * @default
             */
            change_note: string;
        };
        /** StyleVersionInfo */
        StyleVersionInfo: {
            /** Version */
            version: number;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Change Note */
            change_note: string;
            /** Look Hash */
            look_hash: string;
        };
        /**
         * StyleView
         * @description API response for a style: the stored style plus derived, read-only information.
         */
        StyleView: {
            /** Id */
            id: string;
            /** Name */
            name: string;
            /** Description */
            description: string;
            /** Best For */
            best_for: string[];
            /** Avoid On */
            avoid_on: string[];
            /** Values */
            values: {
                [key: string]: unknown;
            };
            /** Rules */
            rules: (components["schemas"]["ExposureRule-Output"] | components["schemas"]["WhiteBalanceRule-Output"])[];
            /** Test Photo Ids */
            test_photo_ids: string[];
            /** Samples */
            samples: components["schemas"]["StyleSampleView"][];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /** Version */
            version: number;
            /** Change Note */
            change_note: string;
            /** Look Hash */
            look_hash: string;
            /**
             * Changed Parameters
             * @description Same as values (what the style changes).
             */
            changed_parameters: {
                [key: string]: unknown;
            };
            /** Cover Url */
            cover_url: string | null;
            /** Photo Count */
            photo_count: number;
            /**
             * Samples Stale
             * @description Some samples show an older look of the style.
             */
            samples_stale: boolean;
        };
        /**
         * SubjectBox
         * @description A box in normalized coordinates (0..1): of the upright photo, unless a field says otherwise.
         */
        SubjectBox: {
            /** Left */
            left: number;
            /** Top */
            top: number;
            /** Right */
            right: number;
            /** Bottom */
            bottom: number;
        };
        /** SubjectCandidate */
        SubjectCandidate: {
            box: components["schemas"]["SubjectBox"];
            kind: components["schemas"]["SubjectKind"];
            /**
             * Score
             * @description How likely this is the photo's main subject.
             */
            score: number;
            /**
             * Label
             * @description What the detector called it, e.g. 'truck'.
             */
            label: string | null;
        };
        /**
         * SubjectInfo
         * @description A photo's main subject: a manual box, the detected one, the AF point, or none.
         */
        SubjectInfo: {
            source: components["schemas"]["SubjectSource"];
            box: components["schemas"]["SubjectBox"] | null;
            kind: components["schemas"]["SubjectKind"] | null;
            /** Score */
            score: number | null;
            /**
             * Candidates
             * @description Everything found, best first (the main subject included).
             */
            candidates: components["schemas"]["SubjectCandidate"][];
            /**
             * Detector
             * @description Identity of the detector that found them.
             */
            detector: string | null;
            /**
             * Notes
             * @description E.g. that the detector model is missing.
             */
            notes: string[];
        };
        /**
         * SubjectKind
         * @enum {string}
         */
        SubjectKind: "car" | "motorcycle" | "aircraft" | "animal" | "person" | "face" | "salient" | "af_point";
        /**
         * SubjectSource
         * @enum {string}
         */
        SubjectSource: "detected" | "manual" | "af_point" | "none";
        /**
         * SubjectUpdate
         * @description Set the photo's subject by hand (upright coordinates), or ``null`` to use the detected one.
         */
        SubjectUpdate: {
            box: components["schemas"]["SubjectBox"] | null;
        };
        /**
         * TiffCompression
         * @enum {string}
         */
        TiffCompression: "none" | "lzw" | "zip";
        /** Tone */
        "Tone-Input": {
            /**
             * Exposure
             * @description Exposure in EV stops.
             * @default 0
             */
            exposure: number;
            /**
             * Contrast
             * @description Global contrast.
             * @default 0
             */
            contrast: number;
            /**
             * Highlights
             * @description Recover (-) or boost (+) bright areas.
             * @default 0
             */
            highlights: number;
            /**
             * Shadows
             * @description Deepen (-) or lift (+) dark areas.
             * @default 0
             */
            shadows: number;
            /**
             * Whites
             * @description White point.
             * @default 0
             */
            whites: number;
            /**
             * Blacks
             * @description Black point.
             * @default 0
             */
            blacks: number;
        };
        /** Tone */
        "Tone-Output": {
            /**
             * Exposure
             * @description Exposure in EV stops.
             * @default 0
             */
            exposure: number;
            /**
             * Contrast
             * @description Global contrast.
             * @default 0
             */
            contrast: number;
            /**
             * Highlights
             * @description Recover (-) or boost (+) bright areas.
             * @default 0
             */
            highlights: number;
            /**
             * Shadows
             * @description Deepen (-) or lift (+) dark areas.
             * @default 0
             */
            shadows: number;
            /**
             * Whites
             * @description White point.
             * @default 0
             */
            whites: number;
            /**
             * Blacks
             * @description Black point.
             * @default 0
             */
            blacks: number;
        };
        /** ToneCurve */
        "ToneCurve-Input": {
            /**
             * Highlights
             * @description Parametric curve: highlights region.
             * @default 0
             */
            highlights: number;
            /**
             * Lights
             * @description Parametric curve: lights region.
             * @default 0
             */
            lights: number;
            /**
             * Darks
             * @description Parametric curve: darks region.
             * @default 0
             */
            darks: number;
            /**
             * Shadows
             * @description Parametric curve: shadows region.
             * @default 0
             */
            shadows: number;
            /** Rgb */
            rgb?: components["schemas"]["CurvePoint"][];
            /** Red */
            red?: components["schemas"]["CurvePoint"][];
            /** Green */
            green?: components["schemas"]["CurvePoint"][];
            /** Blue */
            blue?: components["schemas"]["CurvePoint"][];
        };
        /** ToneCurve */
        "ToneCurve-Output": {
            /**
             * Highlights
             * @description Parametric curve: highlights region.
             * @default 0
             */
            highlights: number;
            /**
             * Lights
             * @description Parametric curve: lights region.
             * @default 0
             */
            lights: number;
            /**
             * Darks
             * @description Parametric curve: darks region.
             * @default 0
             */
            darks: number;
            /**
             * Shadows
             * @description Parametric curve: shadows region.
             * @default 0
             */
            shadows: number;
            /** Rgb */
            rgb: components["schemas"]["CurvePoint"][];
            /** Red */
            red: components["schemas"]["CurvePoint"][];
            /** Green */
            green: components["schemas"]["CurvePoint"][];
            /** Blue */
            blue: components["schemas"]["CurvePoint"][];
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
        /** ValueChange */
        ValueChange: {
            /** Name */
            name: string;
            /**
             * Before
             * @description None = not set by that version.
             */
            before: unknown;
            /** After */
            after: unknown;
        };
        /** Vignette */
        "Vignette-Input": {
            /**
             * Amount
             * @description Darken (-) or lighten (+) the corners.
             * @default 0
             */
            amount: number;
            /**
             * Midpoint
             * @description How far the vignette reaches toward the center.
             * @default 50
             */
            midpoint: number;
            /**
             * Roundness
             * @description Shape: rectangular (-) to circular (+).
             * @default 0
             */
            roundness: number;
            /**
             * Feather
             * @description Softness of the vignette edge.
             * @default 50
             */
            feather: number;
        };
        /** Vignette */
        "Vignette-Output": {
            /**
             * Amount
             * @description Darken (-) or lighten (+) the corners.
             * @default 0
             */
            amount: number;
            /**
             * Midpoint
             * @description How far the vignette reaches toward the center.
             * @default 50
             */
            midpoint: number;
            /**
             * Roundness
             * @description Shape: rectangular (-) to circular (+).
             * @default 0
             */
            roundness: number;
            /**
             * Feather
             * @description Softness of the vignette edge.
             * @default 50
             */
            feather: number;
        };
        /** WhiteBalance */
        "WhiteBalance-Input": {
            /**
             * Temperature
             * @description Color temperature in Kelvin. None = as shot.
             */
            temperature?: number | null;
            /**
             * Tint
             * @description Green (-) / magenta (+) tint. None = as shot.
             */
            tint?: number | null;
        };
        /** WhiteBalance */
        "WhiteBalance-Output": {
            /**
             * Temperature
             * @description Color temperature in Kelvin. None = as shot.
             */
            temperature: number | null;
            /**
             * Tint
             * @description Green (-) / magenta (+) tint. None = as shot.
             */
            tint: number | null;
        };
        /**
         * WhiteBalanceFromPhoto
         * @enum {string}
         */
        WhiteBalanceFromPhoto: "none" | "offset";
        /**
         * WhiteBalanceMode
         * @enum {string}
         */
        WhiteBalanceMode: "as_shot" | "auto" | "fixed";
        /**
         * WhiteBalanceRule
         * @description White balance relative to each photo, instead of a fixed Kelvin value.
         */
        "WhiteBalanceRule-Input": {
            /**
             * Rule Version
             * @description Format version of this rule type.
             * @default 1
             */
            rule_version: number;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "white_balance";
            /**
             * @description as_shot: the camera's white balance plus the offsets. auto: a neutral estimate from the photo plus the offsets (can remove intentional warm light). fixed: temperature and tint as given.
             * @default as_shot
             */
            mode: components["schemas"]["WhiteBalanceMode"];
            /**
             * Temperature Offset
             * @description Kelvin at 5500 K, applied as the same mired shift (looks alike under any light).
             * @default 0
             */
            temperature_offset: number;
            /**
             * Tint Offset
             * @description Added to the tint.
             * @default 0
             */
            tint_offset: number;
            /**
             * Temperature
             * @description Kelvin (fixed mode only).
             */
            temperature?: number | null;
            /**
             * Tint
             * @description Tint (fixed mode only).
             */
            tint?: number | null;
        };
        /**
         * WhiteBalanceRule
         * @description White balance relative to each photo, instead of a fixed Kelvin value.
         */
        "WhiteBalanceRule-Output": {
            /**
             * Rule Version
             * @description Format version of this rule type.
             * @default 1
             */
            rule_version: number;
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            type: "white_balance";
            /**
             * @description as_shot: the camera's white balance plus the offsets. auto: a neutral estimate from the photo plus the offsets (can remove intentional warm light). fixed: temperature and tint as given.
             * @default as_shot
             */
            mode: components["schemas"]["WhiteBalanceMode"];
            /**
             * Temperature Offset
             * @description Kelvin at 5500 K, applied as the same mired shift (looks alike under any light).
             * @default 0
             */
            temperature_offset: number;
            /**
             * Tint Offset
             * @description Added to the tint.
             * @default 0
             */
            tint_offset: number;
            /**
             * Temperature
             * @description Kelvin (fixed mode only).
             */
            temperature: number | null;
            /**
             * Tint
             * @description Tint (fixed mode only).
             */
            tint: number | null;
        };
        /**
         * ZoomInfo
         * @description The zoom view of a photo at one level: tiles of the edited image (after its geometry).
         */
        ZoomInfo: {
            /** @description Percent of the photo's full size: 50 or 100 (1:1). */
            level: components["schemas"]["ZoomLevel"];
            /**
             * State
             * @description 100 % needs the full decode (~13 to 25 s the first time); tiles exist once ready.
             * @enum {string}
             */
            state: "decoding" | "ready";
            /**
             * Width
             * @description The edited image's width at this level.
             */
            width: number | null;
            /** Height */
            height: number | null;
            /**
             * Tile Size
             * @description Tiles are this many pixels square (edge tiles less).
             * @default 512
             */
            tile_size: number;
        };
        /**
         * ZoomLevel
         * @description Zoom view levels in percent of the photo's full size.
         * @enum {integer}
         */
        ZoomLevel: 50 | 100;
        /** ZoomLimits */
        ZoomLimits: {
            /**
             * Fast
             * @description The highest zoom a half-size decode still covers (fast export).
             */
            fast: number;
            /**
             * Quality
             * @description The highest zoom without enlarging (the crop ≥ the output).
             */
            quality: number;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Health"];
                };
            };
        };
    };
    library_api_library_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LibraryInfo"];
                };
            };
        };
    };
    library_folders_api_library_folders_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LibraryFolder"][];
                };
            };
        };
    };
    open_folder_api_library_current_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["OpenFolderRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LibraryInfo"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_folder_api_library_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ImportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Job"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    fs_dirs_api_fs_dirs_get: {
        parameters: {
            query?: {
                /** @description Folder to list; omit for the drives. */
                path?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DirListing"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_photos_api_photos_get: {
        parameters: {
            query?: {
                /** @description Filter by style id; 'none' = photos without a style. */
                style_id?: string | null;
                min_rating?: number;
                sort?: components["schemas"]["PhotoSort"];
                order?: components["schemas"]["SortOrder"];
                offset?: number;
                limit?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Page_Photo_"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    photo_detail_api_photos__photo_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhotoDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    photo_sidecar_api_photos__photo_id__sidecar_get: {
        parameters: {
            query?: {
                /** @description Long edge in pixels. */
                size?: number;
            };
            header?: never;
            path: {
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description JPEG image */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "image/jpeg": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    save_edit_api_photos__photo_id__edit_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AdjustmentParams-Input"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhotoDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reset_edit_api_photos__photo_id__edit_delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhotoDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    change_geometry_api_photos__photo_id__geometry_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GeometryChange"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhotoDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_geometry_api_photos__photo_id__geometry_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["GeometryPreviewRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Geometry-Output"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    photo_subject_api_photos__photo_id__subject_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SubjectInfo"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_photo_subject_api_photos__photo_id__subject_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SubjectUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SubjectInfo"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    suggest_crop_api_photos__photo_id__suggest_crop_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CropSuggestionRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CropSuggestion"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_photo_style_api_photos__photo_id__style_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PhotoStyleRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PhotoDetail"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    engine_api_engine_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EngineInfo"];
                };
            };
        };
    };
    photo_thumbnail_api_photos__photo_id__thumbnail_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description JPEG image */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "image/jpeg": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    photo_preview_api_photos__photo_id__preview_get: {
        parameters: {
            query?: {
                /** @description The photo's default look with the edit's geometry (same framing). */
                before?: boolean;
                /** @description Without any geometry: the whole photo as shot, with its colors (the crop tool). */
                upright?: boolean;
                /** @description Long edge in pixels. */
                size?: number;
            };
            header?: never;
            path: {
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description JPEG image */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "image/jpeg": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    photo_zoom_api_photos__photo_id__zoom__level__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                photo_id: string;
                level: components["schemas"]["ZoomLevel"];
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ZoomInfo"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    photo_tile_api_photos__photo_id__zoom__level__tiles__tx___ty__get: {
        parameters: {
            query?: {
                /** @description The default look with the edit's geometry. */
                before?: boolean;
            };
            header?: never;
            path: {
                photo_id: string;
                level: components["schemas"]["ZoomLevel"];
                tx: number;
                ty: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description JPEG image */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "image/jpeg": unknown;
                };
            };
            /** @description Still decoding: ask /zoom/{level} until ready */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_styles_api_styles_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StyleSummary"][];
                };
            };
        };
    };
    create_style_api_styles_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StyleCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StyleView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    style_api_styles__style_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                style_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StyleView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_style_api_styles__style_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                style_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StyleUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StyleView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_style_api_styles__style_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                style_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StyleDeleted"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_style_from_photo_api_styles_from_photo_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StyleFromPhoto"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StyleView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_style_from_photo_api_styles__style_id__from_photo_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                style_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StyleUpdateFromPhoto"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StyleView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    duplicate_style_api_styles__style_id__duplicate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                style_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StyleDuplicate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StyleView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    style_history_api_styles__style_id__history_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                style_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StyleVersionInfo"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    style_version_api_styles__style_id__versions__version__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                style_id: string;
                version: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StyleView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    style_version_render_api_styles__style_id__versions__version__photos__photo_id__jpg_get: {
        parameters: {
            query?: {
                /** @description Long edge in pixels. */
                size?: number;
            };
            header?: never;
            path: {
                style_id: string;
                version: number;
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description JPEG image */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "image/jpeg": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    style_diff_api_styles__style_id__diff_get: {
        parameters: {
            query: {
                a: number;
                b: number;
            };
            header?: never;
            path: {
                style_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StyleDiff"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    revert_style_api_styles__style_id__revert_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                style_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StyleRevert"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["StyleView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    render_style_samples_api_styles__style_id__samples_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                style_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StyleSamplesRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Job"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    style_report_api_styles__style_id__report_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                style_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StyleReportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ConsistencyReport"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    style_sample_api_styles__style_id__samples__name___which__jpg_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                style_id: string;
                name: string;
                which: "before" | "after";
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description JPEG image */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "image/jpeg": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_presets_api_export_presets_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExportPreset"][];
                };
            };
        };
    };
    create_preset_api_export_presets_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PresetCreate"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExportPreset"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preset_api_export_presets__preset_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                preset_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExportPreset"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_preset_api_export_presets__preset_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                preset_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PresetUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExportPreset"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_preset_api_export_presets__preset_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                preset_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    duplicate_preset_api_export_presets__preset_id__duplicate_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                preset_id: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["PresetDuplicate"] | null;
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExportPreset"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_plan_api_export_plan_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ExportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExportPlan"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_destinations_api_export_destinations_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": string[];
                };
            };
        };
    };
    destination_check_api_export_destination_check_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DestinationCheckRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DestinationCheck"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reveal_export_api_export_reveal_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RevealRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    review_settings_api_review_settings_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReviewSettings-Output"];
                };
            };
        };
    };
    set_review_settings_api_review_settings_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewSettings-Input"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReviewSettings-Output"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_reviews_api_reviews_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ReviewSummary"][];
                };
            };
        };
    };
    get_review_api_reviews__review_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                review_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExportReview"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    discard_review_api_reviews__review_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                review_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_review_item_api_reviews__review_id__items__photo_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                review_id: string;
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewItemUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExportReview"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    set_review_subject_api_reviews__review_id__items__photo_id__subject_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                review_id: string;
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewSubjectUpdate"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ExportReview"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    review_preview_api_reviews__review_id__items__photo_id__preview_get: {
        parameters: {
            query?: {
                /** @description The item's revision (cache busting only). */
                v?: string | null;
            };
            header?: never;
            path: {
                review_id: string;
                photo_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description JPEG image */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "image/jpeg": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_review_api_reviews__review_id__export_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                review_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ReviewExportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Job"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_jobs_api_jobs_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Job"][];
                };
            };
        };
    };
    create_job_api_jobs_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ApplyStyleRequest"] | components["schemas"]["ExportRequest"] | components["schemas"]["ApplyAndExportRequest"] | components["schemas"]["DetectSubjectsRequest"] | components["schemas"]["PrepareExportRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Job"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    job_api_jobs__job_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Job"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_job_api_jobs__job_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                job_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["Job"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
