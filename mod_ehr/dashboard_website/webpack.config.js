const path = require("path");
const webpack = require('webpack');
const CopyWebpackPlugin = require("copy-webpack-plugin");

module.exports = (env) => {
    return {
        entry: {
            index: "./src/index.js",
            dashboard: "./src/dashboard.js",
            appointments: "./src/appointments.js",
            patients: "./src/patients.js",
            common: "./src/common.js",
            usermanagement: "./src/usermanagement.js",
            settingspanel: "./src/settingspanel.js",
            logs: "./src/logs.js",
            hospitals: "./src/hospitals.js",
        },
        output: {
            filename: "[name].js",
            path: path.resolve(__dirname, "dist"),
        },

        plugins: [

            new webpack.DefinePlugin({
                'process.env': JSON.stringify(env),
                // 'process.env.ENV': JSON.stringify(env.ENV || "LOCAL"),
                // 'process.env': {
                //     'ENV': JSON.stringify(env.ENV || "LOCAL"),
                //     'REGION': JSON.stringify(env.REGION || ""),
                //     'POOL_ID': JSON.stringify(env.POOL_ID || ""),
                //     'CLIENT_ID': JSON.stringify(env.CLIENT_ID || ""),
                //     'IDENTITY_POOL_ID': JSON.stringify(env.IDENTITY_POOL_ID || ""),
                //     'GOOGLE_MAPS_KEY': JSON.stringify(env.GOOGLE_MAPS_KEY || ""),
                //     'BASE_URL': JSON.stringify(env.BASE_URL || "")
                // }
            }),

            new CopyWebpackPlugin({
                patterns: [{ from: "src", to: path.resolve(__dirname, "dist") }],
            }),
        ],
        mode: "production",
    }
};
