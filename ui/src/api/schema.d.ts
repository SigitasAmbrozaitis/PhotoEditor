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
        post?: never;
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
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/styles/{style_id}/samples/{n}/{which}.jpg": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Style Sample */
        get: operations["style_sample_api_styles__style_id__samples__n___which__jpg_get"];
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
        post?: never;
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
        put?: never;
        post?: never;
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
        /** Create Job */
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
         * AdjustmentParams
         * @description Complete set of global adjustments. All defaults = identity (no change).
         */
        AdjustmentParams: {
            white_balance?: components["schemas"]["WhiteBalance"];
            tone?: components["schemas"]["Tone"];
            presence?: components["schemas"]["Presence"];
            tone_curve?: components["schemas"]["ToneCurve"];
            hsl?: components["schemas"]["Hsl"];
            color_grading?: components["schemas"]["ColorGrading"];
            detail?: components["schemas"]["Detail"];
            effects?: components["schemas"]["Effects"];
            geometry?: components["schemas"]["Geometry"];
            lens?: components["schemas"]["Lens"];
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
            /** Preset Id */
            preset_id?: string | null;
            settings: components["schemas"]["ExportSettings"];
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
            /** Style Id */
            style_id: string;
        };
        /** AspectSettings */
        AspectSettings: {
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
             * @description What the aspect crop is centered on.
             * @default subject
             */
            anchor: components["schemas"]["CropAnchor"];
        };
        /**
         * CollisionPolicy
         * @enum {string}
         */
        CollisionPolicy: "suffix" | "overwrite" | "skip";
        /** ColorGrading */
        ColorGrading: {
            shadows?: components["schemas"]["GradeWheel"];
            midtones?: components["schemas"]["GradeWheel"];
            highlights?: components["schemas"]["GradeWheel"];
            global?: components["schemas"]["GradeWheel"];
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
        /**
         * CropAnchor
         * @enum {string}
         */
        CropAnchor: "subject" | "center";
        /**
         * CropRect
         * @description Crop rectangle in normalized image coordinates (0..1), applied after rotation.
         */
        CropRect: {
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
        /** Detail */
        Detail: {
            sharpening?: components["schemas"]["Sharpening"];
            noise_reduction?: components["schemas"]["NoiseReduction"];
        };
        /** Effects */
        Effects: {
            vignette?: components["schemas"]["Vignette"];
            grain?: components["schemas"]["Grain"];
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
            settings?: components["schemas"]["ExportSettings"];
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
            settings: components["schemas"]["ExportSettings"];
            /** Destination */
            destination: string;
        };
        /**
         * ExportSettings
         * @description Everything needed to turn an edited photo into an output file.
         */
        ExportSettings: {
            file?: components["schemas"]["FileSettings"];
            /** @default srgb */
            color_space: components["schemas"]["ColorSpace"];
            size?: components["schemas"]["SizeSettings"];
            aspect?: components["schemas"]["AspectSettings"];
            sharpening?: components["schemas"]["OutputSharpening"];
            metadata?: components["schemas"]["MetadataSettings"];
            naming?: components["schemas"]["NamingSettings"];
            /**
             * Destination
             * @description Default output folder. None = ask every time.
             */
            destination?: string | null;
        };
        /**
         * ExportTarget
         * @enum {string}
         */
        ExportTarget: "instagram" | "print" | "web" | "custom";
        /**
         * FileFormat
         * @enum {string}
         */
        FileFormat: "jpeg" | "tiff" | "png";
        /** FileSettings */
        FileSettings: {
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
        };
        /** Geometry */
        Geometry: {
            crop?: components["schemas"]["CropRect"];
            /**
             * Aspect
             * @description Locked aspect ratio such as '4:5'. None = free.
             */
            aspect?: string | null;
            /**
             * Angle
             * @description Straighten / rotate angle in degrees.
             * @default 0
             */
            angle: number;
            /**
             * Flip Horizontal
             * @default false
             */
            flip_horizontal: boolean;
            /**
             * Flip Vertical
             * @default false
             */
            flip_vertical: boolean;
        };
        /** GradeWheel */
        GradeWheel: {
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
        Grain: {
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
        Hsl: {
            red?: components["schemas"]["HslBand"];
            orange?: components["schemas"]["HslBand"];
            yellow?: components["schemas"]["HslBand"];
            green?: components["schemas"]["HslBand"];
            aqua?: components["schemas"]["HslBand"];
            blue?: components["schemas"]["HslBand"];
            purple?: components["schemas"]["HslBand"];
            magenta?: components["schemas"]["HslBand"];
        };
        /** HslBand */
        HslBand: {
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
            finished_at?: string | null;
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
            style_id?: string | null;
            /** Preset Id */
            preset_id?: string | null;
            /** Destination */
            destination?: string | null;
            /** Items */
            items?: components["schemas"]["JobItem"][];
        };
        /** JobItem */
        JobItem: {
            /** Photo Id */
            photo_id: string;
            /** Filename */
            filename: string;
            status: components["schemas"]["JobStatus"];
            /** Message */
            message?: string | null;
            /** Output Path */
            output_path?: string | null;
        };
        /**
         * JobKind
         * @enum {string}
         */
        JobKind: "apply_style" | "export" | "apply_and_export";
        /**
         * JobStatus
         * @enum {string}
         */
        JobStatus: "queued" | "running" | "done" | "failed" | "cancelled";
        /** Lens */
        Lens: {
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
        /** LibraryInfo */
        LibraryInfo: {
            /**
             * Folder
             * @description Currently opened photo folder.
             */
            folder: string | null;
            /** Photo Count */
            photo_count: number;
        };
        /**
         * MetadataPolicy
         * @enum {string}
         */
        MetadataPolicy: "all" | "copyright_only" | "copyright_and_contact" | "all_except_camera_and_gps";
        /** MetadataSettings */
        MetadataSettings: {
            /** @default all_except_camera_and_gps */
            policy: components["schemas"]["MetadataPolicy"];
            /**
             * Strip Gps
             * @default true
             */
            strip_gps: boolean;
            /** Copyright */
            copyright?: string | null;
            /** Keywords */
            keywords?: string[];
        };
        /** NamingSettings */
        NamingSettings: {
            /**
             * Template
             * @description Tokens: {original} {date} {time} {seq} {seq:03} {style} {preset}.
             * @default {original}
             */
            template: string;
            /** @default suffix */
            on_collision: components["schemas"]["CollisionPolicy"];
        };
        /** NoiseReduction */
        NoiseReduction: {
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
        /**
         * Orientation
         * @enum {string}
         */
        Orientation: "auto" | "portrait" | "landscape";
        /** OutputSharpening */
        OutputSharpening: {
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
            captured_at?: string | null;
            /**
             * Camera
             * @description Camera make and model, e.g. 'FUJIFILM X-T3'.
             */
            camera?: string | null;
            /** Lens */
            lens?: string | null;
            /** Iso */
            iso?: number | null;
            /**
             * Shutter
             * @description Exposure time as displayed, e.g. '1/250'.
             */
            shutter?: string | null;
            /**
             * Aperture
             * @description f-number.
             */
            aperture?: number | null;
            /**
             * Focal Length
             * @description Millimetres.
             */
            focal_length?: number | null;
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
             * Rating
             * @default 0
             */
            rating: number;
            /**
             * Style Id
             * @description Style assigned to this photo, if any.
             */
            style_id?: string | null;
            /**
             * Has Overrides
             * @description Per-photo adjustments on top of the style.
             * @default false
             */
            has_overrides: boolean;
        };
        /** PhotoDetail */
        PhotoDetail: {
            photo: components["schemas"]["Photo"];
            edit: components["schemas"]["PhotoEdit"];
        };
        /**
         * PhotoEdit
         * @description The edit of one photo: an optional style plus per-photo overrides. Overrides always win.
         */
        PhotoEdit: {
            /** Photo Id */
            photo_id: string;
            /** Style Id */
            style_id?: string | null;
            /** @description Effective adjustments (style + overrides). */
            adjustments?: components["schemas"]["AdjustmentParams"];
            /**
             * Overridden
             * @description Dotted parameter names that are overridden per photo, e.g. 'tone.exposure'.
             */
            overridden?: string[];
        };
        /**
         * PhotoSort
         * @enum {string}
         */
        PhotoSort: "date" | "name" | "rating";
        /** Presence */
        Presence: {
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
        /**
         * ResizeMode
         * @enum {string}
         */
        ResizeMode: "original" | "long_edge" | "short_edge" | "width_height" | "megapixels" | "percentage";
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
        Sharpening: {
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
        SizeSettings: {
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
        /**
         * SortOrder
         * @enum {string}
         */
        SortOrder: "asc" | "desc";
        /** Style */
        Style: {
            /**
             * Id
             * @description Slug, also the folder name under styles/.
             */
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
             * @description Thumbnail of an 'after' sample.
             */
            cover_url?: string | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
            /**
             * Best For
             * @description Scenes/subjects the style suits.
             */
            best_for?: string[];
            /**
             * Avoid On
             * @description Scenes/subjects the style handles badly.
             */
            avoid_on?: string[];
            adjustments?: components["schemas"]["AdjustmentParams"];
            /** Samples */
            samples?: components["schemas"]["StyleSample"][];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /**
             * Version
             * @description Incremented on every saved change.
             * @default 1
             */
            version: number;
        };
        /**
         * StyleSample
         * @description A before/after example showing the expected result of a style.
         */
        StyleSample: {
            /**
             * Caption
             * @default
             */
            caption: string;
            /** Before Url */
            before_url: string;
            /** After Url */
            after_url: string;
        };
        /** StyleSummary */
        StyleSummary: {
            /**
             * Id
             * @description Slug, also the folder name under styles/.
             */
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
             * @description Thumbnail of an 'after' sample.
             */
            cover_url?: string | null;
            /**
             * Updated At
             * Format: date-time
             */
            updated_at: string;
        };
        /**
         * TiffCompression
         * @enum {string}
         */
        TiffCompression: "none" | "lzw" | "zip";
        /** Tone */
        Tone: {
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
        ToneCurve: {
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
        /** Vignette */
        Vignette: {
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
        WhiteBalance: {
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
                /** @description Show the unedited photo. */
                before?: boolean;
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
                    "application/json": components["schemas"]["Style"];
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
    style_sample_api_styles__style_id__samples__n___which__jpg_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                style_id: string;
                n: number;
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
                "application/json": components["schemas"]["ApplyStyleRequest"] | components["schemas"]["ExportRequest"] | components["schemas"]["ApplyAndExportRequest"];
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
