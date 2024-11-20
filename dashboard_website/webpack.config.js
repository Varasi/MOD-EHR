const path = require("path");
require('dotenv').config({ path: './.env' });
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
            settingspanel: "./src/settingspanel.js"
        },
        output: {
            filename: "[name].js",
            path: path.resolve(__dirname, "dist"),
        },

        plugins: [

            new webpack.DefinePlugin({
                // 'process.env': JSON.stringify(env),
                // 'process.env.ENV': JSON.stringify(env.ENV || "LOCAL"),
                'process.env.REGION': JSON.stringify(process.env.REGION),
                'process.env.POOL_ID': JSON.stringify(process.env.POOL_ID),
                'process.env.CLIENT_ID': JSON.stringify(process.env.CLIENT_ID),
                'process.env.IDENTITY_POOL_ID': JSON.stringify(process.env.IDENTITY_POOL_ID),
                'process.env.BASE_URL': JSON.stringify(process.env.BASE_URL),
                'process.env.GOOGLE_MAPS_KEY': JSON.stringify(process.env.GOOGLE_MAPS_KEY)
            }),

            new CopyWebpackPlugin({
                patterns: [{ from: "src", to: path.resolve(__dirname, "dist") }],
            }),
        ],
        mode: "production",
    }
};
